import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import { searchResources, type SearchResponse } from '~/api';
import type { paths } from '~/api/generated/schema';
import { buildSearchRequest } from '~/search/state/request-builder';
import type { SearchState } from '~/search/state/types';

/**
 * Canonical React Query key for a given search state.
 *
 * Every field that influences the API request must appear here so the cache
 * invalidates correctly on refinement.
 */
export const searchKeys = {
  all: ['search'] as const,
  query: (state: SearchState) =>
    [
      ...searchKeys.all,
      {
        q: state.query,
        resourceType: state.resourceType,
        facets: state.facets,
        sortField: state.sortField,
        sortOrder: state.sortOrder,
        offset: state.offset,
        limit: state.limit,
      },
    ] as const,
};

/**
 * Shared queryOptions factory so loaders and components agree on the exact
 * same key + fetcher. Using queryOptions() (from @tanstack/react-query)
 * preserves type inference end-to-end: the loader's `prefetchQuery` and the
 * component's `useQuery` both get `SearchResponse` back without manual
 * annotation.
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`;
 * client-side callers omit it and get the default browser `apiClient`.
 */
export function searchQueryOptions(state: SearchState, client?: Client<paths>) {
  return queryOptions<SearchResponse>({
    queryKey: searchKeys.query(state),
    queryFn: ({ signal }) =>
      searchResources(buildSearchRequest(state), { signal, client }),
  });
}
