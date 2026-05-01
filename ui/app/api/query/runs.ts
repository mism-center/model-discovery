import { queryOptions } from '@tanstack/react-query';

import {
  getRun,
  isTerminalStatus,
  listModelRuns,
  type ModelRunDetailsResponse,
  type RunDetailResponse,
} from '~/api/endpoints/runs';

export const runKeys = {
  all: ['runs'] as const,
  byModel: (modelId: string) => [...runKeys.all, 'by-model', modelId] as const,
  detail: (runId: string) => [...runKeys.all, 'detail', runId] as const,
};

/**
 * All runs for a given model. Used to discover whether an active (non-terminal)
 * run exists on the search-result card. Disabled by default — cards opt in
 * lazily when the user opens the run controls.
 */
export function modelRunsQueryOptions(modelId: string) {
  return queryOptions<ModelRunDetailsResponse>({
    queryKey: runKeys.byModel(modelId),
    queryFn: ({ signal }) => listModelRuns(modelId, { signal }),
  });
}

/**
 * A single run, with `refresh=true` so the Discovery API hits the Execution
 * service first and we read back fresh status. Polling cadence backs off so
 * long-running jobs don't hammer the API:
 *
 *   - waiting to start (registered): 2s
 *   - running, first 60s: 3s
 *   - running, next 60s: 5s
 *   - running, after 2min total: 10s
 *   - terminal: stop
 *
 * Elapsed time is measured from `started_at` once present, otherwise from
 * `created_at`.
 */
export function runDetailQueryOptions(runId: string) {
  return queryOptions<RunDetailResponse>({
    queryKey: runKeys.detail(runId),
    queryFn: ({ signal }) => getRun(runId, { refresh: true, signal }),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      const { status, started_at, created_at } = data.run;
      if (isTerminalStatus(status)) return false;
      if (status === 'registered') return 2000;
      const startedMs = Date.parse(started_at ?? created_at);
      const elapsed = Number.isFinite(startedMs) ? Date.now() - startedMs : 0;
      if (elapsed < 60_000) return 3000;
      if (elapsed < 120_000) return 5000;
      return 10_000;
    },
  });
}
