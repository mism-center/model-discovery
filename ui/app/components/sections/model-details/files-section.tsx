import {
  ArchiveBoxArrowDownIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  FolderIcon,
} from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';

import type { ResourceFileItem } from '~/api';
import { resourceDownloadUrl } from '~/api';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { EmptyState } from '~/components/common/empty-state';
import { FileTree, useFileTree } from '~/components/common/file-tree';
import { SectionCard } from './primitives';
import { SectionListSkeleton } from './skeleton';

/**
 * Model artifact browser. Renders the listing from
 * `GET /resources/{id}/files` as a collapsible tree; each file downloads via a
 * plain anchor to the download endpoint (anonymous, native browser download),
 * plus a whole-directory zip.
 */
export function FilesSection({ modelId }: { modelId: string }) {
  const { data, isLoading, error, refetch } = useQuery(
    resourceFilesQueryOptions(modelId)
  );

  return (
    <SectionCard title="Files" description="Artifacts stored with this model.">
      <div>
        <FilesBody
          modelId={modelId}
          files={data?.files}
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
  files: ResourceFileItem[] | undefined;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}) {
  // Closed by default: a model's artifact tree is something to navigate, and an
  // opened one is the long listing the tree replaced.
  const tree = useFileTree(files, { initialExpansion: 'none' });

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
    return <SectionListSkeleton rows={5} />;
  }
  if (!files || files.length === 0) {
    return (
      <EmptyState
        icon={FolderIcon}
        title="No files"
        description="Nothing has been stored with this model yet."
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <a
          href={resourceDownloadUrl(modelId)}
          download
          className="flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
        >
          <ArchiveBoxArrowDownIcon aria-hidden="true" className="size-4" />
          Download all (zip)
        </a>
        {tree.hasDirectories && (
          <button
            type="button"
            onClick={() => tree.setAllExpanded(!tree.allExpanded)}
            className="flex items-center gap-1 shrink-0 text-xs font-semibold text-default-800 hover:text-primary cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
          >
            {tree.allExpanded ? (
              <ChevronUpIcon aria-hidden="true" className="size-3.5" />
            ) : (
              <ChevronDownIcon aria-hidden="true" className="size-3.5" />
            )}
            {tree.allExpanded ? 'Collapse all' : 'Expand all'}
          </button>
        )}
      </div>

      <FileTree
        resourceId={modelId}
        nodes={tree.nodes}
        expanded={tree.expanded}
        onToggle={tree.toggle}
      />
    </div>
  );
}
