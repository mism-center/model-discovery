import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import {
  getRun,
  isTerminalStatus,
  listModelRuns,
  listUserRuns,
  type ModelRunDetailsResponse,
  type RunDetailItem,
  type RunDetailResponse,
  type RunStatus,
  type UserRunsResponse,
} from '~/api/endpoints/runs';

export const runKeys = {
  all: ['runs'] as const,
  byModel: (modelId: string) => [...runKeys.all, 'by-model', modelId] as const,
  ownedByModel: (modelId: string) =>
    [...runKeys.all, 'owned-by-model', modelId] as const,
  detail: (runId: string) => [...runKeys.all, 'detail', runId] as const,
  user: (status?: string) => [...runKeys.all, 'user', status ?? 'all'] as const,
};

/**
 * The current user's runs for a model, as bare run records.
 *
 * This mirrors the `owned_runs` embedded in each search result: the search
 * endpoint returns the caller's runs per executable model so the card can
 * render its run controls without a request. Cards seed this query with
 * `initialData: model.owned_runs`, so there's no fetch on first render — a
 * launch invalidates `runKeys.ownedByModel(modelId)` to pull the fresh run in.
 */
export function ownedModelRunsQueryOptions(modelId: string) {
  return queryOptions<RunDetailItem[]>({
    queryKey: runKeys.ownedByModel(modelId),
    queryFn: ({ signal }) =>
      listModelRuns(modelId, { signal }).then((res) =>
        (res.runs ?? []).map((item) => item.run)
      ),
  });
}

/**
 * All runs for a given model. Used to discover whether an active (non-terminal)
 * run exists on the search-result card. Disabled by default — cards opt in
 * lazily when the user opens the run controls.
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient` so run
 * history is fetched as the authenticated user; client-side callers omit it.
 */
export function modelRunsQueryOptions(modelId: string, client?: Client<paths>) {
  return queryOptions<ModelRunDetailsResponse>({
    queryKey: runKeys.byModel(modelId),
    queryFn: ({ signal }) => listModelRuns(modelId, { signal, client }),
  });
}

/**
 * The current user's runs across all models. Requires authentication — the
 * endpoint 401s for anonymous callers, so gate prefetch on an authed user and
 * only enable the client-side query once `useUser()` resolves a user.
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient` so runs
 * are fetched as the authenticated user; client-side callers omit it.
 *
 * Optional `status` filters by a single RunStatus value server-side.
 */
export function userRunsQueryOptions(
  status?: RunStatus,
  client?: Client<paths>
) {
  return queryOptions<UserRunsResponse>({
    queryKey: runKeys.user(status),
    queryFn: ({ signal }) => listUserRuns({ status, signal, client }),
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
