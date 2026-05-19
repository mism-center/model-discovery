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

import '@uppy/core/css/style.min.css';
import '@uppy/dashboard/css/style.min.css';

const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL ?? 'https://20.127.19.251.nip.io/api';

/** Bootstrap endpoint; real URL comes from `POST .../upload` before bytes hit tusd. */
const TUS_ENDPOINT_PLACEHOLDER =
  import.meta.env?.VITE_TUSD_PLACEHOLDER_URL ??
  'https://mism-tusd-dev.renci.org/files/';

type UploadInitiatedResponse = {
  upload_server_base_url: string;
  resource_id: string;
  token: string;
};

function apiOrigin(): string {
  return API_BASE_URL.replace(/\/+$/, '');
}

function tusEndpointFromServerBase(baseUrl: string): string {
  const trimmed = baseUrl.trim().replace(/\/+$/, '');
  if (/\/files$/i.test(trimmed)) return `${trimmed}/`;
  return `${trimmed}/files/`;
}

async function initiateModelUpload(
  modelId: string
): Promise<UploadInitiatedResponse> {
  const url = `${apiOrigin()}/api/v1/models/${encodeURIComponent(modelId)}/upload`;
  const res = await fetch(url, { method: 'POST', credentials: 'include' });
  if (!res.ok) {
    const raw = await res.text();
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === 'string') detail = parsed.detail;
    } catch {
      /* keep raw */
    }
    throw new Error(detail || `Upload init failed (${res.status})`);
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

function createUppy(getModelId: () => string) {
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

    const modelId = getModelId().trim();
    if (!modelId) {
      throw new Error('Enter a model ID, then start the upload.');
    }

    const tusPlugin = uppy.getPlugin('Tus') as
      | { setOptions: (opts: { endpoint: string }) => void }
      | undefined;

    const sessions = await Promise.all(
      fileIDs.map(() => initiateModelUpload(modelId))
    );

    const endpoint = tusEndpointFromServerBase(
      sessions[0].upload_server_base_url
    );
    tusPlugin?.setOptions({ endpoint });

    const pairs = fileIDs.map(
      (id, i) => [id, sessions[i]] as [string, UploadInitiatedResponse]
    );
    for (const [id, s] of pairs) {
      uppy.setFileMeta(id, {
        resource_id: s.resource_id,
        upload_token: '22222222222222222',
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
  const [modelId, setModelId] = useState('');
  const modelIdRef = useRef('');
  modelIdRef.current = modelId;

  const [uppy, setUppy] = useState<Uppy | null>(null);
  const [files, setFiles] = useState<Record<string, FileStatus>>({});

  useEffect(() => {
    const instance = createUppy(() => modelIdRef.current);

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
          Flow:{' '}
          <code>POST {apiOrigin()}/api/v1/models/&lt;model-id&gt;/upload</code>{' '}
          (session cookie) → tus endpoint + <code>resource_id</code> + one-time{' '}
          <code>upload_token</code> on each tus create, matching gateway{' '}
          <code>/api/internal/tusd/hooks</code> pre-create checks.
        </p>
      </header>

      <Card shadow="sm">
        <CardBody className="flex flex-col gap-3">
          <Input
            label="Model ID"
            placeholder="Registry model resource id"
            value={modelId}
            onValueChange={setModelId}
            description="Required before upload. Each file gets a fresh upload token when the batch starts."
          />
        </CardBody>
      </Card>

      <Card shadow="sm">
        <CardBody>
          {uppy ? (
            <Dashboard
              uppy={uppy}
              proudlyDisplayPoweredByUppy={false}
              note="Add files, enter model ID, then Upload. Metadata resource_id and upload_token are set from the gateway right before tus runs."
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
