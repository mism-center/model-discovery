import { createContext, useCallback, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';

import type { ApiError, SearchResponse } from '~/api';
import { searchQueryOptions } from '~/api/query/search';
import { getFacetConfig } from '~/search/state/facets.config';
import {
  hasExplicitFacetParams,
  removeAllFacetParams,
  removeFacetParams,
  searchStateFromParams,
} from '~/search/state/url-codec';
import type {
  FacetValue,
  ResourceType,
  SearchState,
  SortField,
  SortOrder,
} from '~/search/state/types';

/**
 * Thin wrapper around URL state + React Query cache.
 *
 * This context exists for ergonomics — several components need `state`,
 * `data`, and mutators without prop drilling. Anything that only needs the
 * data directly can call `useQuery(searchQueryOptions(state))` itself.
 */
export interface SearchContextValue {
  state: SearchState;

  data: SearchResponse | undefined;

  isLoading: boolean;
  isFetching: boolean;
  error: ApiError | null;

  /** Manually re-trigger the current search. */
  refetch: () => void;

  /** True when the query input is non-empty. Useful in SearchBar's hero/compact split. */
  isCompact: boolean;

  /** True when any facet is active (excludes the resource_type tab). */
  hasActiveFacets: boolean;

  // --- mutators ---
  setQuery: (query: string) => void;
  setResourceType: (resourceType: ResourceType) => void;
  setSort: (field: SortField, order?: SortOrder) => void;
  setOffset: (offset: number) => void;

  /** Read a single facet's current value. */
  getFacet: (id: string) => FacetValue | undefined;
  /** Write a facet. Pass `undefined` to clear. */
  setFacet: (id: string, value: FacetValue | undefined) => void;
  /** Remove a single facet. Equivalent to setFacet(id, undefined). */
  clearFacet: (id: string) => void;
  /** Remove every facet but keep query / tab / sort / pagination. */
  clearAllFacets: () => void;
}

const SearchContext = createContext<SearchContextValue | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const state = useMemo(
    () => searchStateFromParams(searchParams),
    [searchParams]
  );

  const hasActiveFacets = useMemo(
    () => hasExplicitFacetParams(searchParams),
    [searchParams]
  );

  const queryResult = useQuery(searchQueryOptions(state));

  /**
   * Every mutator goes through this helper so we consistently:
   *   - Start from the current URL params.
   *   - Let the caller return a new params object.
   *   - Reset pagination unless the change was the page itself.
   * Resetting offset on every non-pagination change is the right default —
   * any dimension other than the page invalidates the current page number.
   */
  const update = useCallback(
    (
      producer: (current: URLSearchParams) => URLSearchParams,
      options: { keepOffset?: boolean; resetScroll?: boolean } = {}
    ) => {
      setSearchParams(
        (prev) => {
          const next = producer(new URLSearchParams(prev));
          if (!options.keepOffset) next.delete('offset');
          return next;
        },
        // Preserve scroll by default so tweaking a sidebar facet doesn't jump
        // the page; pagination opts into a reset so the next page starts at
        // the top of the results.
        { preventScrollReset: !options.resetScroll }
      );
    },
    [setSearchParams]
  );

  const setQuery = useCallback(
    (query: string) => {
      update((next) => {
        if (query) next.set('q', query);
        else next.delete('q');
        return next;
      });
    },
    [update]
  );

  const setResourceType = useCallback(
    (resourceType: ResourceType) => {
      update((next) => {
        if (resourceType === 'model') next.delete('type');
        else next.set('type', resourceType);
        // Switching tabs wipes facets — the other tab's facets may not
        // exist (e.g. `format_tags` on the models tab).
        return removeAllFacetParams(next);
      });
    },
    [update]
  );

  const setSort = useCallback(
    (field: SortField, order: SortOrder = 'desc') => {
      update((next) => {
        if (field === '_score') next.delete('sort');
        else next.set('sort', field);
        if (order === 'desc') next.delete('order');
        else next.set('order', order);
        return next;
      });
    },
    [update]
  );

  const setOffset = useCallback(
    (offset: number) => {
      update(
        (next) => {
          if (offset > 0) next.set('offset', String(offset));
          else next.delete('offset');
          return next;
        },
        { keepOffset: true, resetScroll: true }
      );
    },
    [update]
  );

  const getFacet = useCallback(
    (id: string) => state.facets[id],
    [state.facets]
  );

  const setFacet = useCallback(
    (id: string, value: FacetValue | undefined) => {
      const config = getFacetConfig(id);
      if (!config) return;
      update((next) => {
        const cleaned = removeFacetParams(id, next);
        if (value) writeFacetValue(id, value, cleaned);
        return cleaned;
      });
    },
    [update]
  );

  const clearFacet = useCallback(
    (id: string) => {
      update((next) => removeFacetParams(id, next));
    },
    [update]
  );

  const clearAllFacets = useCallback(() => {
    update((next) => removeAllFacetParams(next));
  }, [update]);

  const refetch = useCallback(() => {
    // Fire-and-forget; callers just want "try again now".
    void queryResult.refetch();
  }, [queryResult]);

  const value: SearchContextValue = useMemo(
    () => ({
      state,
      data: queryResult.data,
      isLoading: queryResult.isLoading,
      isFetching: queryResult.isFetching,
      error: (queryResult.error as ApiError | null) ?? null,
      refetch,
      // The hero is the landing state, so it collapses as soon as the page
      // carries any search intent — a query *or* an explicit filter. Arriving
      // from a tag link on a model page is intent, so showing the "Find models &
      // data across scales" pitch above the results it already narrowed reads as
      // though the filter had not registered.
      //
      // Safe to collapse because the site header swaps in a compact search input
      // whenever this is true, so the query is still reachable.
      isCompact: state.query.length > 0 || hasActiveFacets,
      hasActiveFacets,
      setQuery,
      setResourceType,
      setSort,
      setOffset,
      getFacet,
      setFacet,
      clearFacet,
      clearAllFacets,
    }),
    [
      state,
      hasActiveFacets,
      queryResult.data,
      queryResult.isLoading,
      queryResult.isFetching,
      queryResult.error,
      refetch,
      setQuery,
      setResourceType,
      setSort,
      setOffset,
      getFacet,
      setFacet,
      clearFacet,
      clearAllFacets,
    ]
  );

  return (
    <SearchContext.Provider value={value}>{children}</SearchContext.Provider>
  );
}

export function useSearch(): SearchContextValue {
  const ctx = useContext(SearchContext);
  if (!ctx) {
    throw new Error('useSearch must be used inside <SearchProvider>');
  }
  return ctx;
}

// ---------- internal ----------

function writeFacetValue(
  id: string,
  value: FacetValue,
  params: URLSearchParams
): void {
  switch (value.kind) {
    case 'terms': {
      for (const v of value.values) params.append(id, v);
      break;
    }
    case 'toggle': {
      if (value.value) params.set(id, 'true');
      break;
    }
    case 'range': {
      if (value.from) params.set(`${id}_from`, value.from);
      if (value.to) params.set(`${id}_to`, value.to);
      break;
    }
  }
}
