import { PlayCircleIcon } from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';

import type { UserRunItem } from '~/api/endpoints/runs';
import { modelRunsQueryOptions } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { EmptyState } from '~/components/common/empty-state';
import { RunRow } from '~/components/sections/runs/run-row';
import { SectionCard } from './primitives';
import { SectionListSkeleton } from './skeleton';

/**
 * This model's execution history.
 *
 * `RunRow` expects a `UserRunItem`, which carries the run's `model`; the
 * model-runs endpoint returns `model` once at the top level plus per-run items
 * without it, so the shared model is grafted onto each item to reuse the row
 * (expand / poll / rerun / terminate) verbatim.
 */
export function RunHistorySection({ modelId }: { modelId: string }) {
  const { data, isLoading, error, refetch } = useQuery(
    modelRunsQueryOptions(modelId)
  );

  const items: UserRunItem[] = (data?.runs ?? []).map((item) => ({
    model: data!.model,
    ...item,
  }));

  return (
    <SectionCard
      title="Run history"
      description="Executions of this model and their outputs."
    >
      <RunHistoryBody
        items={items}
        isLoading={isLoading}
        error={error}
        refetch={refetch}
      />
    </SectionCard>
  );
}

function RunHistoryBody({
  items,
  isLoading,
  error,
  refetch,
}: {
  items: UserRunItem[];
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}) {
  if (error) {
    return (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load run history"
        onRetry={refetch}
      />
    );
  }
  if (isLoading) {
    return <SectionListSkeleton rows={3} />;
  }
  if (items.length === 0) {
    return (
      <EmptyState
        icon={PlayCircleIcon}
        title="No runs yet"
        description="Launch this model to see its execution history here."
      />
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li key={item.run.id}>
          <RunRow item={item} context="single-model" />
        </li>
      ))}
    </ul>
  );
}
