import {
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

import type { components } from '~/api/generated/schema';
import { browserApiBaseUrl, resolveTusdPlaceholderUrl } from '~/utils/env';
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

async function createModel(modelName: string): Promise<ModelResponse> {
  const url = `${apiOrigin()}/api/v1/models`;
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: modelName,
      // Leave empty: the post-finish tus hook stamps `location_uri` to the
      // actual upload directory (`irods:///models/{id}/files`). The API
      // rejects non-iRODS/non-path schemes here at create time.
      location_uri: '',
      execution_type: 'docker',
      description: 'Created by tus upload test page',
    }),
  });

  if (!res.ok) {
    throw new Error(await readApiErrorDetail(res, 'Model creation failed'));
  }

  return res.json() as Promise<ModelResponse>;
}

async function findOrCreateModel(modelName: string): Promise<ModelResponse> {
  const existingModel = await findModelByName(modelName);
  if (existingModel) return existingModel;

  return createModel(modelName);
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

export function meta() {
  return [
    { title: 'Tus Upload Test | MISM' },
    {
      name: 'description',
      content:
        'Test page for tus uploads: gateway upload init, then tusd with hook metadata',
    },
  ];
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

    const model = await findOrCreateModel(modelName);

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

export default function TusTest() {
  const [modelName, setModelName] = useState('');
  const modelNameRef = useRef('');
  modelNameRef.current = modelName;

  const [uppy, setUppy] = useState<Uppy | null>(null);
  const [files, setFiles] = useState<Record<string, FileStatus>>({});

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

  const fileList = Object.values(files);

  return (
    <main className="container mx-auto p-6 flex flex-col gap-6 max-w-4xl">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Tus Upload Test</h1>
        <p className="text-sm text-default-500">
          Flow: <code>GET {apiOrigin()}/api/v1/models?name=&lt;name&gt;</code>{' '}
          (reuse exact name match if found) → otherwise{' '}
          <code>POST {apiOrigin()}/api/v1/models</code> (create model) →{' '}
          <code>POST {apiOrigin()}/api/v1/models/&lt;model-id&gt;/upload</code>{' '}
          (session cookie) → tus endpoint + <code>resource_id</code> + one-time{' '}
          <code>upload_token</code> on each tus create, matching gateway{' '}
          <code>/api/internal/tusd/hooks</code> pre-create checks.
        </p>
      </header>

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
    </main>
  );
}
