import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';

type ApiClientType = Client<paths>;

export type ExecuteRunRequest = components['schemas']['ExecuteRunRequest'];
export type ExecuteRunResponse = components['schemas']['ExecuteRunResponse'];
export type ModelRunDetailsResponse =
  components['schemas']['ModelRunDetailsResponse'];
export type ModelRunDetailItem = components['schemas']['ModelRunDetailItem'];
export type RunDetailResponse = components['schemas']['RunDetailResponse'];
export type RunDetailItem = components['schemas']['RunDetailItem'];
export type RunStatus = components['schemas']['RunStatus'];
export type ResourceSummaryItem = components['schemas']['ResourceSummaryItem'];
export type UserRunsResponse = components['schemas']['UserRunsResponse'];
export type UserRunItem = components['schemas']['UserRunItem'];

/**
 * The subset of a model the launch affordances (RunControls / RunModelModal)
 * actually read. Both `SearchResultItem` and `ModelDetailResponse` satisfy it,
 * so either can drive a launch without coupling the components to one shape.
 */
/**
 * The subset of a model the launch flow needs.
 *
 * `entry_points` is required, not incidental: the run modal lets the user pick
 * one, so narrowing this type without it silently breaks launching from search.
 *
 * `owner` backs `RunControls`' client-side `can_execute` pre-check (MISM-291):
 * the backend relation resolves to true for the model's owner *or* a holder of
 * the platform-wide `executor` role, and owner comparison is the half of that
 * the UI can't get from `useCapabilities()` alone.
 */
export type RunnableModel = Pick<
  components['schemas']['SearchResultItem'],
  'id' | 'name' | 'execution_type' | 'io_spec' | 'entry_points' | 'owner'
> & {
  /**
   * Backs `RunModelModal`'s image-review blocking message (MISM-291).
   * Optional, not `Pick`'d, because `SearchResultItem` doesn't carry this
   * field at all — a known backend/schema gap (see UI-Phase 1-C's deferred
   * finding: list/search views don't surface it). `undefined` is treated
   * the same as `'not_applicable'` — unknown, so don't block on it.
   */
  image_review_status?: string;
  /**
   * Backs `RunModelModal`'s registration-review blocking message (MISM-291).
   * Optional, not `Pick`'d, because `SearchResultItem` doesn't carry this
   * field — search results are always `approved` (the search gate in
   * `RegistryService.search` forces `registration_status=approved` on every
   * query), so there is nothing to block there. `undefined` is treated as
   * not blocked (best-effort); the server-side `validate_registration_approved`
   * check in `prepare_run` remains authoritative either way.
   */
  registration_status?: string;
};

export const TERMINAL_RUN_STATUSES: ReadonlySet<RunStatus> = new Set([
  'completed',
  'failed',
  'cancelled',
]);

export function isTerminalStatus(status: string): boolean {
  return TERMINAL_RUN_STATUSES.has(status as RunStatus);
}

export async function executeModelRun(
  modelId: string,
  body: ExecuteRunRequest,
  options: { signal?: AbortSignal } = {}
): Promise<ExecuteRunResponse> {
  const { data } = await apiClient.POST('/api/v1/models/{model_id}/runs', {
    params: { path: { model_id: modelId } },
    body,
    signal: options.signal,
  });
  return data as ExecuteRunResponse;
}

export async function listModelRuns(
  modelId: string,
  options: {
    status?: RunStatus;
    signal?: AbortSignal;
    client?: ApiClientType;
  } = {}
): Promise<ModelRunDetailsResponse> {
  const { data } = await (options.client ?? apiClient).GET(
    '/api/v1/models/{model_id}/runs',
    {
      params: {
        path: { model_id: modelId },
        query: options.status ? { status: options.status } : {},
      },
      signal: options.signal,
    }
  );
  return data as ModelRunDetailsResponse;
}

export async function listUserRuns(
  options: {
    status?: RunStatus;
    signal?: AbortSignal;
    client?: ApiClientType;
  } = {}
): Promise<UserRunsResponse> {
  const { data } = await (options.client ?? apiClient).GET('/api/v1/me/runs', {
    params: {
      query: options.status ? { status: options.status } : {},
    },
    signal: options.signal,
  });
  return data as UserRunsResponse;
}

export async function getRun(
  runId: string,
  options: { refresh?: boolean; signal?: AbortSignal } = {}
): Promise<RunDetailResponse> {
  const { data } = await apiClient.GET('/api/v1/runs/{run_id}', {
    params: {
      path: { run_id: runId },
      query: options.refresh === undefined ? {} : { refresh: options.refresh },
    },
    signal: options.signal,
  });
  return data as RunDetailResponse;
}

/**
 * Cancel (terminate) a run.
 */
export async function cancelRun(
  runId: string,
  options: { signal?: AbortSignal } = {}
): Promise<RunDetailResponse> {
  const { data } = await apiClient.DELETE('/api/v1/runs/{run_id}', {
    params: { path: { run_id: runId } },
    signal: options.signal,
  });
  return data as RunDetailResponse;
}
