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

/**
 * Pick the run that should be considered "active" for a model.
 *
 * Active = non-terminal. Most-recently created wins so a freshly launched run
 * surfaces immediately even if older non-terminal runs somehow exist.
 *
 * Operates on bare run records (e.g. a model's `owned_runs` from search),
 * which are already scoped to the current user server-side.
 */
export function pickActiveRun(
  runs: RunDetailItem[] | undefined
): RunDetailItem | undefined {
  if (!runs?.length) return undefined;
  const active = runs.filter((run) => !isTerminalStatus(run.status));
  if (active.length === 0) return undefined;
  let latest = active[0];
  for (const current of active) {
    if (current.created_at > latest.created_at) latest = current;
  }
  return latest;
}
