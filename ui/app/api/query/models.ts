import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import {
  getModel,
  getModelAnnotationPackage,
  listModels,
  type MetadataPackageRawResponse,
  type ModelListResponse,
  type RegisterModelResponse,
} from '~/api/endpoints/models';

type ApiClientType = Client<paths>;

export const modelKeys = {
  all: ['models'] as const,
  detail: (modelId: string) => [...modelKeys.all, 'detail', modelId] as const,
  annotationPackage: (modelId: string) =>
    [...modelKeys.all, 'annotation-package', modelId] as const,
  pendingReview: () => [...modelKeys.all, 'pending-review'] as const,
};

export function modelDetailQueryOptions(
  modelId: string,
  client?: ApiClientType
) {
  return queryOptions<RegisterModelResponse>({
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

export function pendingReviewModelsQueryOptions() {
  return queryOptions<ModelListResponse>({
    queryKey: modelKeys.pendingReview(),
    queryFn: ({ signal }) =>
      listModels({ registration_status: 'pending_review', signal }),
  });
}
