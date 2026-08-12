import { useState } from 'react';
import { Spinner, useDisclosure } from '@heroui/react';
import {
  ArrowDownTrayIcon,
  ArchiveBoxArrowDownIcon,
  CodeBracketIcon,
  DocumentIcon,
  DocumentTextIcon,
  EyeIcon,
  PhotoIcon,
  TableCellsIcon,
} from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';

import {
  resourceDownloadUrl,
  type ResourceFileItem,
  type ResourceSummaryItem,
} from '~/api';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { formatBytes } from '~/utils/format';
import { FilePreviewModal, previewCategory } from './file-preview-modal';

interface RunOutputFilesProps {
  outputs: ResourceSummaryItem[];
}

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

function FileTypeIcon({ path }: { path: string }) {
  const extension = path.split('.').pop()?.toLowerCase() ?? '';
  const Icon =
    FILE_TYPE_ICONS.find((entry) => entry.extensions.includes(extension))
      ?.icon ?? DocumentIcon;
  // Inherit color so the parent row's hover state (group-hover:text-primary)
  // applies to the icon too.
  return <Icon aria-hidden="true" className="size-3.5 shrink-0" />;
}

export function RunOutputFiles({ outputs }: RunOutputFilesProps) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-[11px] font-bold uppercase tracking-wider text-default-600">
        Outputs
      </span>
      {outputs.length === 0 ? (
        <p className="text-xs text-default-600">
          This run produced no outputs.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
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

  const preview = useDisclosure();
  const [previewFile, setPreviewFile] = useState<ResourceFileItem | null>(null);
  const openPreview = (file: ResourceFileItem) => {
    setPreviewFile(file);
    preview.onOpen();
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-4">
        <span
          className="text-xs font-semibold text-default-800 truncate"
          title={resource.name}
        >
          {resource.name}
        </span>
        {!isLoading && !isError && files.length > 0 && (
          <a
            href={resourceDownloadUrl(resource.id)}
            download
            className="flex items-center gap-1.5 shrink-0 text-xs font-semibold text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
          >
            <ArchiveBoxArrowDownIcon aria-hidden="true" className="size-3.5" />
            Download zip
          </a>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-default-600 py-1">
          <Spinner size="sm" classNames={{ wrapper: 'w-3 h-3' }} />
          <span>Loading files…</span>
        </div>
      )}

      {isError && (
        <span className="text-xs text-danger py-1">Failed to load files.</span>
      )}

      {!isLoading && !isError && files.length === 0 && (
        <span className="text-xs text-default-600 py-1">No files.</span>
      )}

      {files.length > 0 && (
        <ul className="flex flex-col max-h-40 overflow-auto -mx-1.5">
          {files.map((file) => {
            const category = previewCategory(file.path);
            const isImage = category === 'image';
            const label = (
              <>
                {isImage ? (
                  <img
                    src={resourceDownloadUrl(resource.id, file.path, {
                      inline: true,
                    })}
                    alt=""
                    loading="lazy"
                    className="size-6 shrink-0 rounded object-cover bg-default-100"
                  />
                ) : (
                  <FileTypeIcon path={file.path} />
                )}
                <span className="font-mono truncate">{file.path}</span>
              </>
            );

            return (
              <li key={file.path}>
                {/* Row is a div (not a single anchor) so the preview button
                    and the download link can coexist — a button cannot nest
                    inside an anchor. */}
                <div className="group flex items-center justify-between gap-3 text-xs px-1.5 py-1.5 rounded-md hover:bg-default-100">
                  {category ? (
                    <button
                      type="button"
                      onClick={() => openPreview(file)}
                      aria-label={`Preview ${file.path}`}
                      title={file.path}
                      className="flex items-center gap-2 min-w-0 text-default-800 hover:text-primary transition-colors rounded outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                    >
                      {label}
                    </button>
                  ) : (
                    <span
                      className="flex items-center gap-2 min-w-0 text-default-800"
                      title={file.path}
                    >
                      {label}
                    </span>
                  )}
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="text-default-600 tabular-nums">
                      {formatBytes(file.size_bytes)}
                    </span>
                    {category && (
                      <button
                        type="button"
                        onClick={() => openPreview(file)}
                        aria-label={`Preview ${file.path}`}
                        className="text-default-600 hover:text-primary transition-colors rounded outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                      >
                        <EyeIcon aria-hidden="true" className="size-3.5" />
                      </button>
                    )}
                    <a
                      href={resourceDownloadUrl(resource.id, file.path)}
                      download
                      aria-label={`Download ${file.path}`}
                      className="text-default-600 hover:text-primary transition-colors rounded outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                    >
                      <ArrowDownTrayIcon
                        aria-hidden="true"
                        className="size-3.5"
                      />
                    </a>
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {preview.isOpen && previewFile && (
        <FilePreviewModal
          isOpen
          onClose={preview.onClose}
          resourceId={resource.id}
          file={previewFile}
        />
      )}
    </div>
  );
}
