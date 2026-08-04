import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';

type ApiClientType = Client<paths>;

export type RegisterModelResponse =
  components['schemas']['RegisterModelResponse'];
export type MetadataPackageRawResponse =
  components['schemas']['MetadataPackageRawResponse'];
export type ModelListItem = components['schemas']['ModelListItem'];
export type ModelListResponse = components['schemas']['ModelListResponse'];
export type EntryPointDTO = components['schemas']['EntryPointDTO'];
export type ArgumentDTO = components['schemas']['ArgumentDTO'];
export type ModelDetailResponse = components['schemas']['ModelDetailResponse'];
export type DependencyDTO = components['schemas']['DependencyDTO'];
export type ContainerDTO = components['schemas']['ContainerDTO'];
export type ComputeDTO = components['schemas']['ComputeDTO'];
export type TestSpecDTO = components['schemas']['TestSpecDTO'];
export type IODetailDTO = components['schemas']['IODetailDTO'];
export type ContactDTO = components['schemas']['ContactDTO'];
export type RelatedResourceDTO = components['schemas']['RelatedResourceDTO'];

export async function listModels(
  options: {
    registration_status?: string;
    owner?: string;
    client?: ApiClientType;
    signal?: AbortSignal;
  } = {}
): Promise<ModelListResponse> {
  const { registration_status, owner, client, signal } = options;
  const { data } = await (client ?? apiClient).GET('/api/v1/models', {
    params: {
      query: {
        ...(registration_status ? { registration_status } : {}),
        ...(owner ? { owner } : {}),
        limit: 100,
      },
    },
    signal,
  });
  return data as ModelListResponse;
}

/**
 * Fetch a single model's full detail view (`GET /models/{id}`).
 *
 * Typed as `ModelDetailResponse`: the endpoint returns the characterization
 * fields too, and that type extends `RegisterModelResponse`, so callers needing
 * only the registration subset are unaffected.
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`;
 * client-side callers omit it and use the shared browser client.
 */
export async function getModel(
  modelId: string,
  options: { client?: ApiClientType; signal?: AbortSignal } = {}
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

export async function deleteModel(
  modelId: string,
  options: { signal?: AbortSignal } = {}
): Promise<void> {
  await apiClient.DELETE('/api/v1/models/{model_id}', {
    params: { path: { model_id: modelId } },
    signal: options.signal,
  });
}

export async function getModelAnnotationPackage(
  modelId: string,
  options: { client?: ApiClientType; signal?: AbortSignal } = {}
): Promise<MetadataPackageRawResponse> {
  const { data } = await (options.client ?? apiClient).GET(
    '/api/v1/models/{model_id}/metadata-package/raw',
    {
      params: { path: { model_id: modelId } },
      signal: options.signal,
    }
  );
  return data as MetadataPackageRawResponse;
}
