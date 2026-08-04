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
import { EmptyState } from '~/components/common/empty-state';
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
      <div className="min-h-56">
        <FilesBody
          modelId={modelId}
          files={files}
          isLoading={isLoading}
          error={error}
          refetch={refetch}
        />
      </div>
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
      <div className="flex items-center gap-2 text-sm text-default-800 py-4">
        <Spinner size="sm" classNames={{ wrapper: 'w-4 h-4' }} />
        <span>Loading files…</span>
      </div>
    );
  }
  if (files.length === 0) {
    return (
      <EmptyState
        icon={FolderIcon}
        title="No files"
        description="Nothing has been stored with this model yet."
      />
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {groupByDirectory(files).map(({ directory, entries }) => (
        <div key={directory}>
          {directory !== '' && (
            <p className="flex items-center gap-1.5 mb-1 text-xs font-bold uppercase tracking-wider text-default-800">
              <FolderIcon aria-hidden="true" className="size-3.5 shrink-0" />
              <span className="truncate font-mono normal-case tracking-normal">
                {directory}
              </span>
            </p>
          )}
          <ul className="flex flex-col divide-y divide-default-100">
            {entries.map((file) => (
              <li
                key={file.path}
                className="group flex items-center justify-between gap-4 py-2 px-2 -mx-2 rounded hover:bg-primary/4"
              >
                <div className="flex items-center gap-2 min-w-0 text-default-900">
                  <FileTypeIcon file={file} />
                  <span
                    className="truncate text-sm group-hover:text-primary"
                    title={file.path}
                  >
                    {basename(file.path)}
                  </span>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  {!file.is_dir && (
                    <span className="text-xs text-default-800 tabular-nums">
                      {formatBytes(file.size_bytes)}
                    </span>
                  )}
                  {!file.is_dir && (
                    <a
                      href={resourceDownloadUrl(modelId, file.path)}
                      download
                      aria-label={`Download ${file.path}`}
                      className="text-default-800 group-hover:text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
                    >
                      <ArrowDownTrayIcon className="size-4" />
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** Trailing path segment — the listing is flat, so paths carry the directory. */
function basename(path: string): string {
  const index = path.lastIndexOf('/');
  return index === -1 ? path : path.slice(index + 1);
}

/**
 * Group a flat listing into directory blocks.
 *
 * The API returns one flat array of full paths (and `is_dir` is currently always
 * false), so a real collapsible tree has nothing to expand. Grouping by parent
 * directory gets the structural readability of a tree — you can see the repo's
 * shape and file names stop being long duplicated path strings — without
 * pretending to a hierarchy the endpoint doesn't describe.
 *
 * Root-level files come first (directory `''`), then directories alphabetically.
 */
function groupByDirectory(
  files: ResourceFileItem[]
): Array<{ directory: string; entries: ResourceFileItem[] }> {
  const groups = new Map<string, ResourceFileItem[]>();
  for (const file of files) {
    const index = file.path.lastIndexOf('/');
    const directory = index === -1 ? '' : file.path.slice(0, index);
    const entries = groups.get(directory) ?? [];
    entries.push(file);
    groups.set(directory, entries);
  }
  return (
    [...groups.entries()]
      .map(([directory, entries]) => ({ directory, entries }))
      // eslint-disable-next-line unicorn/no-array-sort -- toSorted needs a newer lib target than tsconfig sets; the array is freshly built above so mutating it is safe
      .sort((a, b) => {
        if (a.directory === '') return -1;
        if (b.directory === '') return 1;
        return a.directory.localeCompare(b.directory);
      })
  );
}
