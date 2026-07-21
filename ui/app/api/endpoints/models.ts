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

export async function getModel(
  modelId: string,
  options: { client?: ApiClientType; signal?: AbortSignal } = {}
): Promise<RegisterModelResponse> {
  const { data } = await (options.client ?? apiClient).GET(
    '/api/v1/models/{model_id}',
    {
      params: { path: { model_id: modelId } },
      signal: options.signal,
    }
  );
  return data as RegisterModelResponse;
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
