import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';

type ApiClientType = Client<paths>;

export type SearchRequest = components['schemas']['SearchRequest'];
export type SearchResponse = components['schemas']['SearchResponse'];
export type SearchFilter = components['schemas']['SearchFilterDTO'];
export type SearchSort = components['schemas']['SearchSortDTO'];
export type SearchResultItem = components['schemas']['SearchResultItem'];
export type AggResult = components['schemas']['AggResultDTO'];
export type AggBucket = components['schemas']['AggBucketDTO'];
export type Author = components['schemas']['AuthorDTO'];
export type Publication = components['schemas']['PublicationDTO'];

/**
 * Full-text + faceted search across models and datasets.
 */
export async function searchResources(
  request: SearchRequest,
  options: { signal?: AbortSignal; client?: ApiClientType } = {}
): Promise<SearchResponse> {
  const { data } = await (options.client ?? apiClient).POST('/api/v1/search', {
    body: request,
    signal: options.signal,
  });
  // errorMiddleware throws on non-2xx, so data is always defined here.
  return data as SearchResponse;
}
