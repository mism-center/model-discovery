import { Button, Spinner } from '@heroui/react';
import {
  ArrowDownTrayIcon,
  ArchiveBoxArrowDownIcon,
} from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';

import { resourceDownloadUrl, type ResourceSummaryItem } from '~/api';
import { resourceFilesQueryOptions } from '~/api/query/resources';

interface RunOutputFilesProps {
  outputs: ResourceSummaryItem[];
}

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
};

export function RunOutputFiles({ outputs }: RunOutputFilesProps) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-bold uppercase tracking-wider text-primary">
        Outputs
      </span>
      {outputs.length === 0 ? (
        <p className="text-xs text-default-600">
          This run produced no outputs.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {outputs.map((resource) => (
            <OutputResourceFiles key={resource.id} resource={resource} />
          ))}
        </div>
      )}
    </div>
  );
}

function OutputResourceFiles({ resource }: { resource: ResourceSummaryItem }) {
  const { data, isLoading, isError } = useQuery(
    resourceFilesQueryOptions(resource.id)
  );

  const files = (data?.files ?? []).filter((f) => !f.is_dir);

  return (
    <div className="flex flex-col gap-2 border border-default-200 rounded-md p-2">
      <span
        className="text-xs font-semibold text-default-800 truncate"
        title={resource.name}
      >
        {resource.name}
      </span>

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-default-600">
          <Spinner size="sm" classNames={{ wrapper: 'w-3 h-3' }} />
          <span>Loading files…</span>
        </div>
      )}

      {isError && (
        <span className="text-xs text-danger">Failed to load files.</span>
      )}

      {!isLoading && !isError && files.length === 0 && (
        <span className="text-xs text-default-600">No files.</span>
      )}

      {files.length > 0 && (
        <ul className="flex flex-col max-h-40 overflow-auto -mx-1">
          {files.map((file) => (
            <li key={file.path}>
              <a
                href={resourceDownloadUrl(resource.id, file.path)}
                download
                aria-label={`Download ${file.path}`}
                className="flex items-center justify-between gap-3 text-xs px-1 py-1 rounded hover:bg-default-100 focus-visible:bg-default-100 outline-none"
              >
                <span
                  className="flex items-center gap-1.5 min-w-0 text-default-800"
                  title={file.path}
                >
                  <ArrowDownTrayIcon className="size-3.5 shrink-0" />
                  <span className="font-mono truncate">{file.path}</span>
                </span>
                <span className="text-default-600 tabular-nums shrink-0">
                  {formatBytes(file.size_bytes)}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}

      {!isLoading && !isError && files.length > 0 && (
        <Button
          as="a"
          href={resourceDownloadUrl(resource.id)}
          download
          size="sm"
          variant="flat"
          color="primary"
          className="w-full font-semibold"
          startContent={<ArchiveBoxArrowDownIcon className="size-4" />}
        >
          Download zip
        </Button>
      )}
    </div>
  );
}
