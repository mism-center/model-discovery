import { Spinner } from '@heroui/react';
import { ArchiveBoxArrowDownIcon } from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';

import { resourceDownloadUrl, type ResourceSummaryItem } from '~/api';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { FileTree, useFileTree } from '~/components/common/file-tree';

interface RunOutputFilesProps {
  outputs: ResourceSummaryItem[];
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

/**
 * One output resource's files, inside a run card.
 *
 * Open by default, unlike the model detail page's tree: a run's outputs are few
 * and the point of the card is seeing what it produced, not navigating to it.
 */
function OutputResourceFiles({ resource }: { resource: ResourceSummaryItem }) {
  const { data, isLoading, isError } = useQuery(
    resourceFilesQueryOptions(resource.id)
  );
  const files = data?.files;
  const tree = useFileTree(files, { initialExpansion: 'all' });

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-4">
        <span
          className="text-xs font-semibold text-default-800 truncate"
          title={resource.name}
        >
          {resource.name}
        </span>
        {!isLoading && !isError && files && files.length > 0 && (
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

      {!isLoading && !isError && files?.length === 0 && (
        <span className="text-xs text-default-600 py-1">No files.</span>
      )}

      {files && files.length > 0 && (
        <div className="max-h-40 overflow-auto -mx-1.5">
          <FileTree
            resourceId={resource.id}
            nodes={tree.nodes}
            expanded={tree.expanded}
            onToggle={tree.toggle}
            density="compact"
            thumbnails
          />
        </div>
      )}
    </div>
  );
}
