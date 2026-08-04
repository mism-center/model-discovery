import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  Input,
  Progress,
} from '@heroui/react';
import Uppy, { type Body, type Meta, type UppyFile } from '@uppy/core';
import Dashboard from '@uppy/react/dashboard';
import Tus from '@uppy/tus';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';

import { requireUser } from '~/api/auth/require-user';
import type { components } from '~/api/generated/schema';
import { MetadataFormViewer } from '~/components/sections/upload/metadata-form-viewer';
import { browserApiBaseUrl, resolveTusdPlaceholderUrl } from '~/utils/env';
import type { Route } from './+types/upload';
import '@uppy/core/css/style.min.css';
import '@uppy/dashboard/css/style.min.css';

/** Bootstrap endpoint default; real URL comes from `POST .../upload` before bytes hit tusd. */
const TUS_ENDPOINT_PLACEHOLDER = resolveTusdPlaceholderUrl();

type UploadInitiatedResponse = {
  upload_server_base_url: string;
  resource_id: string;
  token: string;
};

type ModelListItem = components['schemas']['ModelListItem'];
type ModelListResponse = components['schemas']['ModelListResponse'];
type ModelResponse = Pick<ModelListItem, 'id' | 'name'>;

type GitHubImportApiResponse = {
  model_id: string;
  branch: string;
  files_extracted: number;
  size_bytes: number;
  location_uri: string;
};

type ExecuteRunApiResponse = {
  run_id: string;
};

type WorkflowStep =
  | 'idle'
  | 'Initializing'
  | 'importing'
  | 'annotating'
  | 'monitoring'
  | 'complete'
  | 'error'
  | 'aborted';

function apiOrigin(): string {
  return browserApiBaseUrl().replace(/\/+$/, '');
}

function tusEndpointFromServerBase(baseUrl: string): string {
  const trimmed = baseUrl.trim().replace(/\/+$/, '');
  if (/\/files$/i.test(trimmed)) return `${trimmed}/`;
  return `${trimmed}/files/`;
}

async function readApiErrorDetail(
  res: Response,
  fallbackMessage: string
): Promise<string> {
  const raw = await res.text();
  let detail = raw;
  try {
    const parsed = JSON.parse(raw) as {
      detail?: unknown;
      error?: {
        detail?: unknown;
      };
    };
    if (typeof parsed.error?.detail === 'string') {
      detail = parsed.error.detail;
    } else if (typeof parsed.detail === 'string') {
      detail = parsed.detail;
    }
  } catch {
    /* keep raw */
  }

  return detail || `${fallbackMessage} (${res.status})`;
}

async function findModelByName(
  modelName: string
): Promise<ModelResponse | null> {
  const limit = 100;
  let offset = 0;

  while (true) {
    const params = new URLSearchParams({
      name: modelName,
      limit: String(limit),
      offset: String(offset),
    });
    const url = `${apiOrigin()}/api/v1/models?${params.toString()}`;
    const res = await fetch(url, { credentials: 'include' });

    if (!res.ok) {
      throw new Error(await readApiErrorDetail(res, 'Model lookup failed'));
    }

    const payload = (await res.json()) as ModelListResponse;
    const match = payload.results.find((model) => model.name === modelName);
    if (match) return match;

    offset += payload.results.length;
    if (offset >= payload.total || payload.results.length === 0) return null;
  }
}

async function createModel(
  modelName: string,
  description: string
): Promise<ModelResponse> {
  const url = `${apiOrigin()}/api/v1/models`;
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: modelName,
      // Placeholder iRODS URI — must be non-empty to satisfy registry validation.
      // The TUS post-finish hook (file upload) or mark_upload_complete (GitHub
      // import) overwrites this with the real path once data lands in iRODS.
      location_uri: 'irods:///pending',
      execution_type: 'docker',
      version: '0.0.1',
      description,
    }),
  });

  if (!res.ok) {
    throw new Error(await readApiErrorDetail(res, 'Model creation failed'));
  }

  return res.json() as Promise<ModelResponse>;
}

async function findOrCreateModel(
  modelName: string,
  description: string
): Promise<ModelResponse> {
  const existingModel = await findModelByName(modelName);
  if (existingModel) return existingModel;

  return createModel(modelName, description);
}

async function initiateModelUpload(
  modelId: string
): Promise<UploadInitiatedResponse> {
  const url = `${apiOrigin()}/api/v1/models/${encodeURIComponent(modelId)}/upload`;
  const res = await fetch(url, { method: 'POST', credentials: 'include' });
  if (!res.ok) {
    throw new Error(await readApiErrorDetail(res, 'Upload init failed'));
  }

  return res.json() as Promise<UploadInitiatedResponse>;
}

async function initiateAnnotation(
  modelId: string
): Promise<ExecuteRunApiResponse> {
  const res = await fetch(
    `${apiOrigin()}/api/v1/runs/${encodeURIComponent(modelId)}`,
    { method: 'POST', credentials: 'include' }
  );
  if (!res.ok)
    throw new Error(await readApiErrorDetail(res, 'Annotation launch failed'));
  return res.json() as Promise<ExecuteRunApiResponse>;
}

async function fetchModelStatus(modelId: string): Promise<string | null> {
  const res = await fetch(
    `${apiOrigin()}/api/v1/models/${encodeURIComponent(modelId)}`,
    { credentials: 'include' }
  );
  if (!res.ok) return null;
  const data = (await res.json()) as { registration_status?: string };
  return data.registration_status ?? null;
}

async function fetchAnnotationPackage(modelId: string): Promise<{
  files: { filename: string; content: string }[];
  registryId: string;
} | null> {
  const res = await fetch(
    `${apiOrigin()}/api/v1/models/${encodeURIComponent(modelId)}/metadata-package/raw`,
    { credentials: 'include' }
  );
  if (!res.ok) return null;
  const data = (await res.json()) as {
    files?: { filename: string; content: string }[];
  };
  return { files: data.files ?? [], registryId: modelId };
}

type ResourceFileItem = components['schemas']['ResourceFileItem'];

async function fetchAnnotationOutputFiles(
  resourceId: string
): Promise<ResourceFileItem[] | null> {
  const res = await fetch(
    `${apiOrigin()}/api/v1/resources/${encodeURIComponent(resourceId)}/files`,
    { credentials: 'include' }
  );
  if (!res.ok) return null;
  const data =
    (await res.json()) as components['schemas']['ResourceFilesResponse'];
  return (data.files ?? []).filter(
    (f) =>
      !f.is_dir &&
      f.path.startsWith('metadata-package/') &&
      !f.name.startsWith('.')
  );
}

async function importFromGitHub(
  modelId: string,
  githubUrl: string
): Promise<GitHubImportApiResponse> {
  const url = `${apiOrigin()}/api/v1/models/${encodeURIComponent(modelId)}/github-import`;
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  });
  if (!res.ok) {
    throw new Error(await readApiErrorDetail(res, 'GitHub import failed'));
  }
  return res.json() as Promise<GitHubImportApiResponse>;
}

export function meta() {
  return [
    { title: 'Model Upload | MISM' },
    {
      name: 'description',
      content: 'Upload a model file or import a GitHub repository into MISM.',
    },
  ];
}

/**
 * Auth-gated route, mirroring `runs.tsx` and `annotation-review.tsx`.
 *
 * Uploading requires a session — the initiate-upload and GitHub-import endpoints
 * both reject anonymous callers — so the gate belongs at the boundary rather than
 * letting someone fill in the whole form and only discover that on submit.
 *
 * Nothing is prefetched: this page has no server-fetched queries, and the root
 * loader already hydrates the user for `useUser()`.
 */
export async function loader({ request }: Route.LoaderArgs) {
  await requireUser(request, { returnToKey: 'upload' });
  return null;
}

type FileStatus = {
  id: string;
  name: string;
  size: number;
  resourceId: string;
  progress: number;
  status: 'queued' | 'uploading' | 'complete' | 'error';
  error?: string;
  uploadUrl?: string;
};

function createUppy(getModelName: () => string) {
  const uppy = new Uppy({
    autoProceed: false,
    restrictions: { maxNumberOfFiles: 10 },
  }).use(Tus, {
    endpoint: TUS_ENDPOINT_PLACEHOLDER,
    retryDelays: [0, 1000, 3000, 5000],
    chunkSize: 5 * 1024 * 1024,
    removeFingerprintOnSuccess: true,
    allowedMetaFields: [
      'resource_id',
      'upload_token',
      'filename',
      'filetype',
      'type',
    ],
  });

  uppy.addPreProcessor(async (fileIDs) => {
    if (fileIDs.length === 0) return;

    const modelName = getModelName().trim();
    if (!modelName) {
      throw new Error('Enter a model name, then start the upload.');
    }

    const tusPlugin = uppy.getPlugin('Tus') as
      | { setOptions: (opts: { endpoint: string }) => void }
      | undefined;

    const model = await findOrCreateModel(modelName, 'Created via file upload');

    const sessions = await Promise.all(
      fileIDs.map(() => initiateModelUpload(model.id))
    );

    const endpoint = tusEndpointFromServerBase(
      sessions[0].upload_server_base_url
    );
    tusPlugin?.setOptions({ endpoint });

    const pairs = fileIDs.map(
      (id, i) => [id, sessions[i]] as [string, UploadInitiatedResponse]
    );
    for (const [id, s] of pairs) {
      const file = uppy.getFile(id);
      uppy.setFileMeta(id, {
        resource_id: s.resource_id,
        upload_token: s.token,
        filename: file?.name ?? 'upload.bin',
        filetype: file?.type ?? '',
      });
    }
  });

  return uppy;
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function statusColor(status: FileStatus['status']) {
  switch (status) {
    case 'complete': {
      return 'success';
    }
    case 'uploading': {
      return 'primary';
    }
    case 'error': {
      return 'danger';
    }
    default: {
      return 'default';
    }
  }
}

type StepDef = {
  key: WorkflowStep;
  label: string;
};

const GITHUB_STEPS: StepDef[] = [
  { key: 'Initializing', label: 'Initialize workflow' },
  { key: 'importing', label: 'Download & extract repository' },
  { key: 'annotating', label: 'Initiate annotation run' },
  { key: 'monitoring', label: 'Monitor annotation' },
];

const STEP_ORDER: WorkflowStep[] = [
  'Initializing',
  'importing',
  'annotating',
  'monitoring',
  'complete',
];

const TERMINAL_STATUSES = new Set([
  'pending_review',
  'approved',
  'annotation_failed',
  'rejected',
]);

function stepChipColor(
  stepKey: WorkflowStep,
  currentStep: WorkflowStep,
  failedStep: WorkflowStep
): 'default' | 'primary' | 'success' | 'danger' {
  if (currentStep === 'aborted') {
    const monitoringIdx = STEP_ORDER.indexOf('monitoring');
    const stepIdx = STEP_ORDER.indexOf(stepKey);
    return stepIdx < monitoringIdx ? 'success' : 'default';
  }
  if (currentStep === 'error') {
    const failedIdx = STEP_ORDER.indexOf(failedStep);
    const stepIdx = STEP_ORDER.indexOf(stepKey);
    if (stepIdx < failedIdx) return 'success';
    if (stepIdx === failedIdx) return 'danger';
    return 'default';
  }
  const currentIdx = STEP_ORDER.indexOf(currentStep);
  const stepIdx = STEP_ORDER.indexOf(stepKey);
  if (stepIdx < currentIdx) return 'success';
  if (stepIdx === currentIdx) return 'primary';
  return 'default';
}

export default function TusTest() {
  const navigate = useNavigate();
  const [modelName, setModelName] = useState('');
  const modelNameRef = useRef('');
  modelNameRef.current = modelName;

  const [uppy, setUppy] = useState<Uppy | null>(null);
  const [files, setFiles] = useState<Record<string, FileStatus>>({});

  // GitHub import workflow state
  const [mode, setMode] = useState<'file' | 'github'>('github');
  const [githubUrl, setGithubUrl] = useState('');
  const [workflowStep, setWorkflowStep] = useState<WorkflowStep>('idle');
  const [failedStep, setFailedStep] = useState<WorkflowStep>('idle');
  const [registeredModelId, setRegisteredModelId] = useState('');
  const [importError, setImportError] = useState('');
  const [annotationStatus, setAnnotationStatus] = useState('');
  const [rawFiles, setRawFiles] = useState<
    { filename: string; content: string }[]
  >([]);
  const [metadataRegistryId, setMetadataRegistryId] = useState('');
  const [metadataSaveState, setMetadataSaveState] = useState<
    'idle' | 'saving' | 'saved' | 'error'
  >('idle');
  const [metadataSaveError, setMetadataSaveError] = useState('');
  const [outputFiles, setOutputFiles] = useState<ResourceFileItem[] | null>(
    null
  );

  useEffect(() => {
    const instance = createUppy(() => modelNameRef.current);

    const upsert = <M extends Meta, B extends Body>(
      file: UppyFile<M, B>,
      patch: Partial<FileStatus>
    ) => {
      setFiles((prev) => {
        const existing = prev[file.id];
        return {
          ...prev,
          [file.id]: {
            id: file.id,
            name: file.name ?? existing?.name ?? '(unnamed)',
            size: file.size ?? existing?.size ?? 0,
            resourceId:
              (file.meta?.resource_id as string | undefined) ??
              existing?.resourceId ??
              '',
            progress: existing?.progress ?? 0,
            status: existing?.status ?? 'queued',
            ...patch,
          },
        };
      });
    };

    instance.on('file-added', (file) => {
      upsert(file, { status: 'queued', progress: 0 });
    });

    instance.on('upload', (_id, uploadingFiles) => {
      for (const file of uploadingFiles) {
        upsert(file, { status: 'uploading' });
      }
    });

    instance.on('upload-progress', (file, progress) => {
      if (!file) return;
      const pct =
        progress.bytesTotal && progress.bytesTotal > 0
          ? Math.round((progress.bytesUploaded / progress.bytesTotal) * 100)
          : 0;
      upsert(file, { status: 'uploading', progress: pct });
    });

    instance.on('upload-success', (file, response) => {
      if (!file) return;
      upsert(file, {
        status: 'complete',
        progress: 100,
        uploadUrl: response?.uploadURL ?? undefined,
      });
    });

    instance.on('upload-error', (file, error) => {
      if (!file) return;
      upsert(file, { status: 'error', error: error?.message ?? String(error) });
    });

    instance.on('file-removed', (file) => {
      setFiles((prev) => {
        const next = { ...prev };
        delete next[file.id];
        return next;
      });
    });

    setUppy(instance);

    return () => {
      instance.destroy();
    };
  }, []);

  useEffect(() => {
    if (workflowStep !== 'monitoring' || !registeredModelId) return;

    const intervalId = setInterval(() => {
      void (async () => {
        const status = await fetchModelStatus(registeredModelId);
        if (!status) return;
        setAnnotationStatus(status);
        if (TERMINAL_STATUSES.has(status)) {
          clearInterval(intervalId);
          if (status === 'annotation_failed' || status === 'rejected') {
            setFailedStep('monitoring');
            setImportError(
              `Annotation ended with status: ${status}. Check execution logs.`
            );
            setWorkflowStep('error');
          } else {
            const [metaResult, files] = await Promise.all([
              fetchAnnotationPackage(registeredModelId),
              fetchAnnotationOutputFiles(registeredModelId),
            ]);
            setRawFiles(metaResult?.files ?? []);
            setMetadataRegistryId(metaResult?.registryId ?? '');
            setMetadataSaveState('idle');
            setOutputFiles(files);
            setWorkflowStep('complete');
          }
        }
      })();
    }, 10_000);

    return () => clearInterval(intervalId);
  }, [workflowStep, registeredModelId]);

  async function handleDebugJumpToComplete() {
    const resourceId = import.meta.env
      .VITE_DEBUG_ANNOTATION_RESOURCE_ID as string;
    setImportError('');
    setAnnotationStatus('pending_review');
    setRawFiles([]);
    setMetadataRegistryId('');
    setMetadataSaveState('idle');
    setMetadataSaveError('');
    setOutputFiles(null);
    setFailedStep('idle');
    setRegisteredModelId(resourceId);
    setWorkflowStep('complete');
    const [metaResult, files] = await Promise.all([
      fetchAnnotationPackage(resourceId),
      fetchAnnotationOutputFiles(resourceId),
    ]);
    setRawFiles(metaResult?.files ?? []);
    setMetadataRegistryId(metaResult?.registryId ?? '');
    setOutputFiles(files);
  }

  async function handleGitHubImport() {
    const name = modelName.trim();
    const url = githubUrl.trim();
    if (!name || !url) return;

    setImportError('');
    setRegisteredModelId('');
    setAnnotationStatus('');
    setRawFiles([]);
    setOutputFiles(null);
    setFailedStep('idle');

    // Track current step locally so the catch block can report it accurately,
    // independent of React's batched state updates.
    let activeStep: WorkflowStep = 'idle';

    try {
      // Step 1: register (or reuse) the model.
      activeStep = 'Initializing';
      setWorkflowStep('Initializing');
      const model = await findOrCreateModel(name, 'Created via GitHub import');
      setRegisteredModelId(model.id);

      // Step 2: download tarball and extract files into iRODS.
      activeStep = 'importing';
      setWorkflowStep('importing');
      await importFromGitHub(model.id, url);

      // Step 3: launch annotation run.
      activeStep = 'annotating';
      setWorkflowStep('annotating');
      await initiateAnnotation(model.id);

      setAnnotationStatus('annotating');
      setWorkflowStep('monitoring');
    } catch (error: unknown) {
      setFailedStep(activeStep);
      setImportError(error instanceof Error ? error.message : String(error));
      setWorkflowStep('error');
    }
  }

  const fileList = Object.values(files);
  const isRunning =
    workflowStep === 'Initializing' ||
    workflowStep === 'importing' ||
    workflowStep === 'annotating' ||
    workflowStep === 'monitoring';

  return (
    <main className="container mx-auto p-6 flex flex-col gap-6 max-w-4xl">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Model Upload</h1>
        <p className="text-sm text-foreground">
          Register a model from a GitHub repository or upload a file directly
          via TUS.
        </p>
      </header>

      {/* Mode toggle */}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant={mode === 'github' ? 'solid' : 'bordered'}
          color={mode === 'github' ? 'primary' : 'default'}
          onPress={() => setMode('github')}
        >
          Import from GitHub
        </Button>
        <Button
          size="sm"
          variant={mode === 'file' ? 'solid' : 'bordered'}
          color={mode === 'file' ? 'primary' : 'default'}
          onPress={() => setMode('file')}
        >
          Upload File
        </Button>
      </div>

      {/* Debug banner — only rendered when VITE_DEBUG_ANNOTATION_RESOURCE_ID is set */}
      {import.meta.env.VITE_DEBUG_ANNOTATION_RESOURCE_ID && (
        <Card shadow="none" className="border border-warning-300 bg-warning-50">
          <CardBody className="flex flex-row items-center justify-between gap-4 py-2">
            <span className="text-xs text-warning-700">
              Debug · resource{' '}
              <code className="font-mono">
                {import.meta.env.VITE_DEBUG_ANNOTATION_RESOURCE_ID}
              </code>
            </span>
            <Button
              size="sm"
              color="warning"
              variant="flat"
              isDisabled={isRunning}
              onPress={() => void handleDebugJumpToComplete()}
            >
              Jump to annotation complete
            </Button>
          </CardBody>
        </Card>
      )}

      {mode === 'github' ? (
        <>
          {/* GitHub import inputs */}
          <Card shadow="sm">
            <CardBody className="flex flex-col gap-3">
              <Input
                label="Model name"
                placeholder="Name for the model to reuse or create"
                value={modelName}
                onValueChange={setModelName}
                isDisabled={isRunning}
                description="Reuses an existing exact-name match when found; otherwise creates a new model."
              />
              <Input
                label="GitHub repository URL"
                placeholder="https://github.com/owner/repo"
                value={githubUrl}
                onValueChange={setGithubUrl}
                isDisabled={isRunning}
                description="Public repository URL. Optionally include a branch: /tree/branch-name."
              />
              <Button
                color="primary"
                isDisabled={!modelName.trim() || !githubUrl.trim() || isRunning}
                isLoading={isRunning}
                onPress={() => void handleGitHubImport()}
              >
                Import &amp; Annotate
              </Button>
            </CardBody>
          </Card>

          {/* Step progress */}
          {workflowStep !== 'idle' && (
            <Card shadow="sm">
              <CardHeader className="flex flex-col items-start gap-0">
                <h2 className="text-lg font-medium">Workflow progress</h2>
              </CardHeader>
              <CardBody className="flex flex-col gap-3">
                {GITHUB_STEPS.map((step) => {
                  const color = stepChipColor(
                    step.key,
                    workflowStep,
                    failedStep
                  );

                  let label = 'pending';

                  if (color === 'success') {
                    label = 'done';
                  } else if (color === 'danger') {
                    label = 'failed';
                  } else if (workflowStep === step.key) {
                    label = 'running…';
                  } else if (workflowStep === 'error' && color === 'default') {
                    label = 'skipped';
                  }

                  return (
                    <div
                      key={step.key}
                      className="flex items-center justify-between gap-2"
                    >
                      <span className="text-sm">{step.label}</span>
                      <Chip
                        size="sm"
                        color={color}
                        variant={color === 'success' ? 'solid' : 'flat'}
                      >
                        {label}
                      </Chip>
                    </div>
                  );
                })}
              </CardBody>
            </Card>
          )}

          {/* Aborted notice */}
          {workflowStep === 'aborted' && (
            <Card shadow="sm" className="border-warning-300 bg-warning-50">
              <CardBody className="flex flex-col gap-1">
                <span className="text-sm font-medium text-foreground">
                  Monitoring aborted
                </span>
                <span className="text-xs text-foreground">
                  Polling stopped. The annotation job may still be running in
                  the background — check back later or start a new import.
                </span>
                <div className="mt-2">
                  <Button
                    size="sm"
                    color="warning"
                    variant="flat"
                    className="text-foreground"
                    onPress={() => navigate('/search')}
                  >
                    Return to the Search page
                  </Button>
                </div>
              </CardBody>
            </Card>
          )}

          {/* Monitoring notification */}
          {workflowStep === 'monitoring' && (
            <Card shadow="sm" className="border-primary-300 bg-primary-100">
              <CardBody className="flex flex-col gap-1">
                <span className="text-sm font-medium text-primary-900">
                  Annotation running…
                </span>
                <span className="text-xs text-primary-800">
                  Status:{' '}
                  <code className="font-mono">
                    {annotationStatus || 'annotating'}
                  </code>
                </span>
                {registeredModelId && (
                  <span className="text-xs text-primary-800">
                    Model ID:{' '}
                    <code className="font-mono">{registeredModelId}</code>
                  </span>
                )}
                <span className="text-xs text-primary-700">
                  Polling every 10 s — will update automatically.
                </span>
                <Button
                  size="sm"
                  color="warning"
                  variant="flat"
                  className="mt-1 w-fit text-foreground"
                  onPress={() => setWorkflowStep('aborted')}
                >
                  Abort
                </Button>
              </CardBody>
            </Card>
          )}

          {/* Success notification */}
          {workflowStep === 'complete' && (
            <Card shadow="sm" className="border-success-200 bg-success-50">
              <CardBody className="flex flex-col gap-1">
                <span className="text-lg font-medium text-foreground">
                  Annotation complete
                </span>
                {annotationStatus && (
                  <span className="text-xs text-default-800">
                    Status:{' '}
                    <code className="font-mono font-bold text-default-900">
                      {annotationStatus}
                    </code>
                  </span>
                )}
                {registeredModelId && (
                  <span className="text-xs text-default-800">
                    Model ID:{' '}
                    <code className="font-mono">{registeredModelId}</code>
                  </span>
                )}
                {/* Re-annotate button hidden temporarily */}
                {rawFiles.length > 0 && (
                  <div className="mt-2">
                    <MetadataFormViewer
                      modelId={metadataRegistryId}
                      rawFiles={rawFiles}
                      onSaved={() => {
                        setMetadataSaveState('saved');
                        setAnnotationStatus('approved');
                      }}
                      onSaveError={(msg) => {
                        setMetadataSaveState('error');
                        setMetadataSaveError(msg);
                      }}
                      annotationFiles={(outputFiles ?? []).map((f) => ({
                        path: f.path,
                        name: f.name,
                        url: `${apiOrigin()}/api/v1/resources/${encodeURIComponent(registeredModelId)}/download?${new URLSearchParams({ file: f.path }).toString()}`,
                      }))}
                    />
                    {metadataSaveState === 'error' && (
                      <span className="text-xs text-danger-600 mt-1">
                        {metadataSaveError}
                      </span>
                    )}
                  </div>
                )}
                <div className="mt-3">
                  <Button
                    size="sm"
                    color="success"
                    variant="flat"
                    className="text-foreground"
                    onPress={() => navigate('/search')}
                  >
                    Return to the Search page
                  </Button>
                </div>
              </CardBody>
            </Card>
          )}

          {/* Error notification */}
          {workflowStep === 'error' && (
            <Card shadow="sm" className="border-danger-200 bg-danger-50">
              <CardBody>
                <span className="text-sm text-danger-700">{importError}</span>
              </CardBody>
            </Card>
          )}
        </>
      ) : (
        <>
          {/* Existing TUS file upload */}
          <Card shadow="sm">
            <CardBody className="flex flex-col gap-3">
              <Input
                label="Model name"
                placeholder="Name for the model to reuse or create"
                value={modelName}
                onValueChange={setModelName}
                description="Required before upload. The page reuses an existing exact-name match when found; otherwise it creates a model before requesting upload tokens."
              />
            </CardBody>
          </Card>

          <Card shadow="sm">
            <CardBody>
              {uppy ? (
                <Dashboard
                  uppy={uppy}
                  proudlyDisplayPoweredByUppy={false}
                  note="Add files, enter a model name, then Upload. The page reuses or creates the model, then sets resource_id and upload_token from the gateway right before tus runs."
                  height={420}
                />
              ) : (
                <div className="p-8 text-center text-default-500">
                  Initializing uploader…
                </div>
              )}
            </CardBody>
          </Card>

          {fileList.length > 0 && (
            <Card shadow="sm">
              <CardHeader className="flex flex-col items-start gap-0">
                <h2 className="text-lg font-medium">Upload progress</h2>
                <p className="text-xs text-default-500">
                  {fileList.length} file{fileList.length === 1 ? '' : 's'}
                </p>
              </CardHeader>
              <CardBody className="flex flex-col gap-4">
                {fileList.map((f) => (
                  <div key={f.id} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex flex-col min-w-0">
                        <span className="font-medium truncate">{f.name}</span>
                        <span className="text-xs text-default-500 truncate">
                          resource_id: <code>{f.resourceId || '—'}</code> ·{' '}
                          {formatBytes(f.size)}
                        </span>
                      </div>
                      <Chip
                        size="sm"
                        color={statusColor(f.status)}
                        variant={f.status === 'complete' ? 'solid' : 'flat'}
                      >
                        {f.status === 'complete' ? 'uploaded' : f.status}
                      </Chip>
                    </div>
                    <Progress
                      aria-label={`Upload progress for ${f.name}`}
                      value={f.progress}
                      color={statusColor(f.status)}
                      size="sm"
                    />
                    {f.status === 'complete' && f.uploadUrl && (
                      <span className="text-xs text-success-600 truncate">
                        URL: <code>{f.uploadUrl}</code>
                      </span>
                    )}
                    {f.status === 'error' && f.error && (
                      <span className="text-xs text-danger-600">{f.error}</span>
                    )}
                  </div>
                ))}
              </CardBody>
            </Card>
          )}
        </>
      )}
    </main>
  );
}
