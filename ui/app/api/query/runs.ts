import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import {
  getRun,
  isTerminalStatus,
  listModelRuns,
  listUserRuns,
  type ModelRunDetailsResponse,
  type RunDetailResponse,
  type RunStatus,
  type UserRunsResponse,
} from '~/api/endpoints/runs';

export const runKeys = {
  all: ['runs'] as const,
  byModel: (modelId: string) => [...runKeys.all, 'by-model', modelId] as const,
  detail: (runId: string) => [...runKeys.all, 'detail', runId] as const,
  user: (status?: string) => [...runKeys.all, 'user', status ?? 'all'] as const,
};

/**
 * All runs for a given model (`GET /models/{id}/runs`).
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
    // Poll while any run in the list is still non-terminal so status (and the
    // derived duration) stay fresh even for collapsed rows, which don't run
    // their own detail query. Stop once every run has reached a terminal state.
    refetchInterval: (query) => {
      const runs = query.state.data?.runs ?? [];
      const anyActive = runs.some((item) => !isTerminalStatus(item.run.status));
      return anyActive ? 5000 : false;
    },
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
