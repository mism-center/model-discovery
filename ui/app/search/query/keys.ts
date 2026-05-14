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
