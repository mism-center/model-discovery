import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import { ApiError } from '~/api/client/errors';
import type { paths } from '~/api/generated/schema';
import {
  getModel,
  getModelAnnotationPackage,
  listModels,
  type MetadataPackageRawResponse,
  type ModelDetailResponse,
  type ModelListResponse,
} from '~/api/endpoints/models';

type ApiClientType = Client<paths>;

export const modelKeys = {
  all: ['models'] as const,
  detail: (modelId: string) => [...modelKeys.all, 'detail', modelId] as const,
  annotationPackage: (modelId: string) =>
    [...modelKeys.all, 'annotation-package', modelId] as const,
  pendingReview: () => [...modelKeys.all, 'pending-review'] as const,
  imageReviewQueue: () => [...modelKeys.all, 'image-review-queue'] as const,
  pendingImageReview: (userId: string) =>
    [...modelKeys.all, 'pending-image-review', userId] as const,
};

/**
 * A single model's full detail view (`GET /models/{id}`).
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`;
 * client-side callers omit it.
 */
export function modelDetailQueryOptions(
  modelId: string,
  client?: ApiClientType
) {
  return queryOptions<ModelDetailResponse>({
    queryKey: modelKeys.detail(modelId),
    queryFn: ({ signal }) => getModel(modelId, { client, signal }),
  });
}

/**
 * Retries for a package that 404s. The annotation job writes it from another
 * pod, so it can reach the API's mount a few seconds after the model flips to
 * `pending_review`, and the API 404s rather than waiting for it.
 */
const PACKAGE_NOT_FOUND_RETRIES = 4;

/**
 * A model's raw annotation YAML (`GET /models/{id}/metadata-package/raw`).
 *
 * SSR loaders should pass `retry: false`: a 404 is expected while annotation
 * is running, and the retries would hold the navigation open.
 */
export function modelAnnotationPackageQueryOptions(
  modelId: string,
  client?: ApiClientType
) {
  return queryOptions<MetadataPackageRawResponse>({
    queryKey: modelKeys.annotationPackage(modelId),
    queryFn: ({ signal }) =>
      getModelAnnotationPackage(modelId, { client, signal }),
    retry: (failureCount, error) =>
      failureCount <
      (error instanceof ApiError && error.status === 404
        ? PACKAGE_NOT_FOUND_RETRIES
        : 1),
  });
}

/**
 * Models pending metadata review (`GET /models?registration_status=pending_review`).
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`,
 * matching `modelDetailQueryOptions`'s pattern — added for UI-Phase 4-A's
 * dedicated page; the pre-existing search-results embedded section (the
 * only prior caller) still omits it and uses the browser `apiClient`.
 */
export function pendingReviewModelsQueryOptions(client?: ApiClientType) {
  return queryOptions<ModelListResponse>({
    queryKey: modelKeys.pendingReview(),
    queryFn: ({ signal }) =>
      listModels({ registration_status: 'pending_review', client, signal }),
  });
}

/**
 * Models awaiting Dockerfile/image review
 * (`image_review_status=pending_image_check`), for the Image Review
 * queue (MISM-291, UI-Phase 6-A).
 */
export function imageReviewQueueModelsQueryOptions(client?: ApiClientType) {
  return queryOptions<ModelListResponse>({
    queryKey: modelKeys.imageReviewQueue(),
    queryFn: ({ signal }) =>
      listModels({
        image_review_status: 'pending_image_check',
        client,
        signal,
      }),
  });
}

/**
 * The current user's own models awaiting Dockerfile/image review
 * (`image_review_status=pending_image_check`), for the owner-facing
 * "Image Pending Review" section embedded in search results.
 *
 * Cache key is per-user so two users sharing a browser session never see
 * each other's data.
 */
export function pendingImageReviewModelsQueryOptions(
  userId: string,
  client?: ApiClientType
) {
  return queryOptions<ModelListResponse>({
    queryKey: modelKeys.pendingImageReview(userId),
    queryFn: ({ signal }) =>
      listModels({
        image_review_status: 'pending_image_check',
        owner: userId,
        client,
        signal,
      }),
  });
}
