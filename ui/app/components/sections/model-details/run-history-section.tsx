import { Spinner } from '@heroui/react';
import { useQuery } from '@tanstack/react-query';

import type { UserRunItem } from '~/api/endpoints/runs';
import { modelRunsQueryOptions } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { RunRow } from '~/components/sections/runs/run-row';
import { SectionCard } from './primitives';

/**
 * This model's execution history. `RunRow` expects a `UserRunItem` (which
 * carries the run's `model`); the model-runs endpoint returns `model` once at
 * the top level plus per-run items without it, so we graft the shared model
 * onto each item to reuse the row (expand / poll / rerun / terminate) verbatim.
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
    return (
      <div className="flex items-center gap-2 text-sm text-default-600 py-4">
        <Spinner size="sm" classNames={{ wrapper: 'w-4 h-4' }} />
        <span>Loading runs…</span>
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <p className="text-sm text-default-500 py-2">
        This model hasn&apos;t been run yet.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li key={item.run.id}>
          <RunRow item={item} />
        </li>
      ))}
    </ul>
  );
}
