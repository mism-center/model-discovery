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
 */
export type RunnableModel = Pick<
  components['schemas']['SearchResultItem'],
  'id' | 'name' | 'execution_type' | 'io_spec' | 'entry_points'
>;

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
