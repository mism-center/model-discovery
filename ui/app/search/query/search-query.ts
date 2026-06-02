import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import { searchResources, type SearchResponse } from '~/api';
import type { paths } from '~/api/generated/schema';
import { buildSearchRequest } from '~/search/state/request-builder';
import type { SearchState } from '~/search/state/types';
import { searchKeys } from './keys';

/**
 * Shared queryOptions factory so loaders and components agree on the exact
 * same key + fetcher. Using queryOptions() (from @tanstack/react-query)
 * preserves type inference end-to-end: the loader's `ensureQueryData` and
 * the component's `useQuery` both get `SearchResponse` back without manual
 * annotation.
 *
 * Pass `client` from SSR loaders (the per-request `serverApiClient`) so the
 * fetch has an absolute base URL and the forwarded cookie. Browser callers
 * omit it and fall back to the relative-origin `apiClient`.
 */
export function searchQueryOptions(state: SearchState, client?: Client<paths>) {
  return queryOptions<SearchResponse>({
    queryKey: searchKeys.query(state),
    queryFn: ({ signal }) =>
      searchResources(buildSearchRequest(state), { signal, client }),
  });
}
