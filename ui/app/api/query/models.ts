import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import { getModel, type ModelDetailResponse } from '~/api/endpoints/models';

export const modelKeys = {
  all: ['models'] as const,
  detail: (modelId: string) => [...modelKeys.all, 'detail', modelId] as const,
};

/**
 * A single model's full detail view (`GET /models/{id}`).
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`;
 * client-side callers omit it.
 */
export function modelDetailQueryOptions(
  modelId: string,
  client?: Client<paths>
) {
  return queryOptions<ModelDetailResponse>({
    queryKey: modelKeys.detail(modelId),
    queryFn: ({ signal }) => getModel(modelId, { signal, client }),
  });
}
