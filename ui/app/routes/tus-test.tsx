import { Card, CardBody, CardHeader, Chip, Progress } from '@heroui/react';
import Uppy, { type Body, type Meta, type UppyFile } from '@uppy/core';
import Dashboard from '@uppy/react/dashboard';
import Tus from '@uppy/tus';
import { useEffect, useState } from 'react';

import '@uppy/core/css/style.min.css';
import '@uppy/dashboard/css/style.min.css';

const TUS_ENDPOINT = 'https://mism-tusd-dev.renci.org/files/';

export function meta() {
  return [
    { title: 'Tus Upload Test | MISM' },
    {
      name: 'description',
      content: 'Test page for uploading files via tus to the MISM tusd server',
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

function createUppy(
  onResourceId: (fileId: string, resourceId: string) => void
) {
  const uppy = new Uppy({
    autoProceed: false,
    restrictions: { maxNumberOfFiles: 10 },
  }).use(Tus, {
    endpoint: TUS_ENDPOINT,
    retryDelays: [0, 1000, 3000, 5000],
    chunkSize: 5 * 1024 * 1024,
    removeFingerprintOnSuccess: true,
  });

  // assign a fresh resource_id to every newly added file so tus-js-client
  // base64-encodes it into the Upload-Metadata header as `resource_id <b64>`
  uppy.on('file-added', (file) => {
    const resourceId = crypto.randomUUID();
    uppy.setFileMeta(file.id, { resource_id: resourceId });
    onResourceId(file.id, resourceId);
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
  const [uppy, setUppy] = useState<Uppy | null>(null);
  const [files, setFiles] = useState<Record<string, FileStatus>>({});

  useEffect(() => {
    const instance = createUppy((fileId, resourceId) => {
      setFiles((prev) => ({
        ...prev,
        [fileId]: {
          id: fileId,
          name: prev[fileId]?.name ?? '',
          size: prev[fileId]?.size ?? 0,
          resourceId,
          progress: 0,
          status: 'queued',
        },
      }));
    });

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
          Uploads to <code>{TUS_ENDPOINT}</code> via Uppy + tus. A random UUID
          is generated per file and sent as <code>resource_id</code> in the{' '}
          <code>Upload-Metadata</code> header.
        </p>
      </header>

      <Card shadow="sm">
        <CardBody>
          {uppy ? (
            <Dashboard
              uppy={uppy}
              proudlyDisplayPoweredByUppy={false}
              note="Drop files here or click to browse. A random resource_id UUID is attached per file."
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
                      resource_id: <code>{f.resourceId}</code> ·{' '}
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
