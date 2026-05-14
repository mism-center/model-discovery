import { queryOptions } from '@tanstack/react-query';

import { searchResources, type SearchResponse } from '~/api';
import { buildSearchRequest } from '~/search/state/request-builder';
import type { SearchState } from '~/search/state/types';
import { searchKeys } from './keys';

/**
 * Shared queryOptions factory so loaders and components agree on the exact
 * same key + fetcher. Using queryOptions() (from @tanstack/react-query)
 * preserves type inference end-to-end: the loader's `ensureQueryData` and
 * the component's `useQuery` both get `SearchResponse` back without manual
 * annotation.
 */
export function searchQueryOptions(state: SearchState) {
  return queryOptions<SearchResponse>({
    queryKey: searchKeys.query(state),
    queryFn: ({ signal }) =>
      searchResources(buildSearchRequest(state), { signal }),
  });
}
