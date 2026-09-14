import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

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

export function modelAnnotationPackageQueryOptions(
  modelId: string,
  client?: ApiClientType
) {
  return queryOptions<MetadataPackageRawResponse>({
    queryKey: modelKeys.annotationPackage(modelId),
    queryFn: ({ signal }) =>
      getModelAnnotationPackage(modelId, { client, signal }),
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
