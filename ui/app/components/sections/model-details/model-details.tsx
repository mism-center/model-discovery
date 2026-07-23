import { useQuery } from '@tanstack/react-query';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { modelDetailQueryOptions } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { ExecutionSection } from './execution-section';
import { FilesSection } from './files-section';
import { IOSpecSection } from './io-spec-section';
import { MetadataSidebar } from './metadata-sidebar';
import { ModelHeader } from './model-header';
import { RunHistorySection } from './run-history-section';
import { ModelDetailsSkeleton } from './skeleton';

/**
 * Model details page body. Two-column on `lg+` (stacked sections + sticky
 * metadata sidebar), single column below. Sections that have no data render
 * nothing, so sparsely-annotated models stay uncluttered.
 */
export function ModelDetailsSection({ modelId }: { modelId: string }) {
  const {
    data: model,
    isLoading,
    error,
    refetch,
  } = useQuery(modelDetailQueryOptions(modelId));

  return (
    <main className="flex flex-col grow bg-default-50">
      <div className="w-full max-w-6xl mx-auto px-6 py-8">
        <Body
          modelId={modelId}
          model={model}
          isLoading={isLoading}
          error={error}
          refetch={refetch}
        />
      </div>
    </main>
  );
}

function Body({
  modelId,
  model,
  isLoading,
  error,
  refetch,
}: {
  modelId: string;
  model: ModelDetailResponse | undefined;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}) {
  if (error) {
    return (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load this model"
        onRetry={refetch}
      />
    );
  }
  if (isLoading || !model) {
    return <ModelDetailsSkeleton />;
  }
  return (
    <div className="flex flex-col gap-8">
      <ModelHeader model={model} />
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-8 items-start">
        <div className="flex flex-col gap-6 min-w-0">
          <IOSpecSection model={model} />
          <ExecutionSection model={model} />
          <FilesSection modelId={modelId} />
          <RunHistorySection modelId={modelId} />
        </div>
        <MetadataSidebar model={model} />
      </div>
    </div>
  );
}
