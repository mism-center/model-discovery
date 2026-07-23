import { Spinner } from '@heroui/react';
import {
  ArchiveBoxArrowDownIcon,
  ArrowDownTrayIcon,
  CodeBracketIcon,
  DocumentIcon,
  DocumentTextIcon,
  FolderIcon,
  PhotoIcon,
  TableCellsIcon,
} from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';

import type { ResourceFileItem } from '~/api';
import { resourceDownloadUrl } from '~/api';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { formatBytes } from '~/utils/format';
import { SectionCard } from './primitives';

const FILE_TYPE_ICONS: Array<{
  extensions: string[];
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}> = [
  {
    extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff'],
    icon: PhotoIcon,
  },
  {
    extensions: ['csv', 'tsv', 'xlsx', 'xls', 'parquet'],
    icon: TableCellsIcon,
  },
  { extensions: ['json', 'yaml', 'yml', 'xml', 'toml'], icon: CodeBracketIcon },
  { extensions: ['txt', 'md', 'log'], icon: DocumentTextIcon },
];

function FileTypeIcon({ file }: { file: ResourceFileItem }) {
  if (file.is_dir)
    return <FolderIcon aria-hidden="true" className="size-4 shrink-0" />;
  const extension = file.path.split('.').pop()?.toLowerCase() ?? '';
  const Icon =
    FILE_TYPE_ICONS.find((entry) => entry.extensions.includes(extension))
      ?.icon ?? DocumentIcon;
  return <Icon aria-hidden="true" className="size-4 shrink-0" />;
}

/** Sort directories first, then alphabetically by path. */
function sortFiles(files: ResourceFileItem[]): ResourceFileItem[] {
  // eslint-disable-next-line unicorn/no-array-sort -- toSorted needs a newer lib target than tsconfig sets
  return [...files].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
    return a.path.localeCompare(b.path);
  });
}

/**
 * Model artifact browser. Renders the flat file listing from
 * `GET /resources/{id}/files`; each file downloads via a plain anchor to the
 * download endpoint (anonymous, native browser download), plus a
 * whole-directory zip.
 */
export function FilesSection({ modelId }: { modelId: string }) {
  const { data, isLoading, error, refetch } = useQuery(
    resourceFilesQueryOptions(modelId)
  );

  const files = sortFiles(data?.files ?? []);

  return (
    <SectionCard
      title="Files"
      description="Artifacts stored with this model."
      action={
        !isLoading && !error && files.length > 0 ? (
          <a
            href={resourceDownloadUrl(modelId)}
            download
            className="flex items-center gap-1.5 shrink-0 text-sm font-semibold text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
          >
            <ArchiveBoxArrowDownIcon aria-hidden="true" className="size-4" />
            Download all (zip)
          </a>
        ) : undefined
      }
    >
      <FilesBody
        modelId={modelId}
        files={files}
        isLoading={isLoading}
        error={error}
        refetch={refetch}
      />
    </SectionCard>
  );
}

function FilesBody({
  modelId,
  files,
  isLoading,
  error,
  refetch,
}: {
  modelId: string;
  files: ResourceFileItem[];
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}) {
  if (error) {
    return (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load files"
        onRetry={refetch}
      />
    );
  }
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-default-600 py-4">
        <Spinner size="sm" classNames={{ wrapper: 'w-4 h-4' }} />
        <span>Loading files…</span>
      </div>
    );
  }
  if (files.length === 0) {
    return (
      <p className="text-sm text-default-500 py-2">
        No files are stored with this model.
      </p>
    );
  }
  return (
    <ul className="flex flex-col divide-y divide-default-100">
      {files.map((file) => (
        <li
          key={file.path}
          className="group flex items-center justify-between gap-4 py-2"
        >
          <div className="flex items-center gap-2 min-w-0 text-default-800">
            <FileTypeIcon file={file} />
            <span className="truncate text-[13px]" title={file.path}>
              {file.path}
            </span>
          </div>
          <div className="flex items-center gap-4 shrink-0">
            {!file.is_dir && typeof file.size_bytes === 'number' && (
              <span className="text-[12px] text-default-500 tabular-nums">
                {formatBytes(file.size_bytes)}
              </span>
            )}
            {!file.is_dir && (
              <a
                href={resourceDownloadUrl(modelId, file.path)}
                download
                aria-label={`Download ${file.path}`}
                className="text-default-500 hover:text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
              >
                <ArrowDownTrayIcon className="size-4" />
              </a>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
