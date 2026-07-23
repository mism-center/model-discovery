import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';

type ApiClientType = Client<paths>;

export type ModelDetailResponse = components['schemas']['ModelDetailResponse'];
export type DependencyDTO = components['schemas']['DependencyDTO'];
export type ContainerDTO = components['schemas']['ContainerDTO'];
export type ComputeDTO = components['schemas']['ComputeDTO'];
export type EntryPointDTO = components['schemas']['EntryPointDTO'];
export type ArgumentDTO = components['schemas']['ArgumentDTO'];
export type TestSpecDTO = components['schemas']['TestSpecDTO'];

/**
 * Fetch a single model's full detail view (`GET /models/{id}`).
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`;
 * client-side callers omit it and use the shared browser client.
 */
export async function getModel(
  modelId: string,
  options: { signal?: AbortSignal; client?: ApiClientType } = {}
): Promise<ModelDetailResponse> {
  const { data } = await (options.client ?? apiClient).GET(
    '/api/v1/models/{model_id}',
    {
      params: { path: { model_id: modelId } },
      signal: options.signal,
    }
  );
  return data as ModelDetailResponse;
}
