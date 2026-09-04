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
 * (`image_review_status === 'pending_image_check'`), for the Image Review
 * queue (MISM-291, UI-Phase 6-A).
 *
 * Unlike `pendingReviewModelsQueryOptions`, `GET /models` has no
 * `image_review_status` filter param at all — confirmed against
 * `list_models` in `mismapi/api/v1/models.py`, only `registration_status`
 * is filterable server-side. So this filters client-side over the
 * `registration_status=approved` page (the only registration status
 * `pending_image_check` can occur under). Inherits `listModels`'s
 * hardcoded `limit: 100`, so a store with more than 100 approved models
 * could hide a pending-image-check candidate beyond that page — the same
 * known cap `pendingReviewModelsQueryOptions` already accepts, not a new
 * limitation introduced here.
 *
 * Unlike the pending-review queue's ownership-only visibility gap
 * (UI-Phase 4-A), `approved` is the one registration status
 * `model_visible_to()` treats as fully public (`PUBLIC_REGISTRATION_STATUSES`
 * in `_authz.py`) — so every candidate model here is visible to every
 * caller regardless of role, and this queue has no equivalent
 * backend-visibility limitation to document.
 */
export function imageReviewQueueModelsQueryOptions(client?: ApiClientType) {
  return queryOptions<ModelListResponse>({
    queryKey: modelKeys.imageReviewQueue(),
    queryFn: async ({ signal }) => {
      const response = await listModels({
        registration_status: 'approved',
        client,
        signal,
      });
      const results = response.results.filter(
        (m) => m.image_review_status === 'pending_image_check'
      );
      return { total: results.length, results };
    },
  });
}

/**
 * The current user's own models awaiting Dockerfile/image review
 * (`image_review_status === 'pending_image_check'`), for the owner-facing
 * "Image Pending Review" section embedded in search results.
 *
 * Differs from `imageReviewQueueModelsQueryOptions` (the reviewer's queue) in
 * two ways: (1) it passes `owner: userId` so only the caller's own models are
 * returned, and (2) the cache key is keyed per user so two different users
 * browsing the same browser session never see each other's data.
 *
 * Like `imageReviewQueueModelsQueryOptions`, the client-side filter is
 * necessary because `GET /models` has no `image_review_status` query param —
 * only `registration_status` is filterable server-side.
 */
export function pendingImageReviewModelsQueryOptions(
  userId: string,
  client?: ApiClientType
) {
  return queryOptions<ModelListResponse>({
    queryKey: modelKeys.pendingImageReview(userId),
    queryFn: async ({ signal }) => {
      const response = await listModels({
        registration_status: 'approved',
        owner: userId,
        client,
        signal,
      });
      const results = response.results.filter(
        (m) => m.image_review_status === 'pending_image_check'
      );
      return { total: results.length, results };
    },
  });
}
