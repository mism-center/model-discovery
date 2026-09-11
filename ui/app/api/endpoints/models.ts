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
export type ReviewMetadataPackageRequest =
  components['schemas']['ReviewMetadataPackageRequest'];
export type SubmitContainerImageRequest =
  components['schemas']['SubmitContainerImageRequest'];
export type ReviewContainerImageRequest =
  components['schemas']['ReviewContainerImageRequest'];

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

/**
 * An UPLOAD_REVIEWER's approve/reject decision on a PENDING_REVIEW model
 * (`POST /models/{id}/review`, MISM-291).
 */
export async function reviewModelMetadata(
  modelId: string,
  body: ReviewMetadataPackageRequest,
  options: { signal?: AbortSignal } = {}
): Promise<RegisterModelResponse> {
  const { data } = await apiClient.POST('/api/v1/models/{model_id}/review', {
    params: { path: { model_id: modelId } },
    body,
    signal: options.signal,
  });
  return data as RegisterModelResponse;
}

/**
 * Submit (or resubmit after rejection) a built Dockerfile/image for
 * IMAGE_CHECK review (`POST /models/{id}/image`, MISM-291). Requires the
 * model's metadata registration to already be `APPROVED`.
 */
export async function submitModelContainerImage(
  modelId: string,
  body: SubmitContainerImageRequest,
  options: { signal?: AbortSignal } = {}
): Promise<RegisterModelResponse> {
  const { data } = await apiClient.POST('/api/v1/models/{model_id}/image', {
    params: { path: { model_id: modelId } },
    body,
    signal: options.signal,
  });
  return data as RegisterModelResponse;
}

/**
 * An IMAGE_CHECK holder's approve/reject decision on a PENDING_IMAGE_CHECK
 * model's Dockerfile/image (`POST /models/{id}/image-review`, MISM-291).
 */
export async function reviewModelContainerImage(
  modelId: string,
  body: ReviewContainerImageRequest,
  options: { signal?: AbortSignal } = {}
): Promise<RegisterModelResponse> {
  const { data } = await apiClient.POST(
    '/api/v1/models/{model_id}/image-review',
    {
      params: { path: { model_id: modelId } },
      body,
      signal: options.signal,
    }
  );
  return data as RegisterModelResponse;
}
