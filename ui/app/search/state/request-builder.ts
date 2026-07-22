import type { SearchFilter, SearchRequest } from '~/api';
import { facetsForResourceType, type FacetConfig } from './facets.config';
import type { FacetValue, SearchState } from './types';

/**
 * Compile a typed SearchState into the API's SearchRequest DTO.
 *
 * Rules:
 *  - The active tab becomes a `resource_type eq <tab>` filter.
 *  - Each facet value compiles to one or two SearchFilterDTOs:
 *      terms  → { op: <facet.termsOp>, value: string[] }
 *               (`overlap` for array-valued backend fields, `in` for scalars —
 *                declared per-facet in facets.config.ts)
 *      toggle → { op: 'eq', value: true }  (only when true)
 *      range  → { op: 'gte', ... } and/or { op: 'lte', ... }
 *  - `aggs` requests buckets for every facet visible on the active tab, so
 *    the sidebar always has counts to render. Range facets are skipped —
 *    the backend's term aggregation doesn't apply to date fields and
 *    we don't render bucket lists for ranges anyway.
 */
export function buildSearchRequest(state: SearchState): SearchRequest {
  const visibleFacets = facetsForResourceType(state.resourceType);

  const filters: SearchFilter[] = [
    { field: 'resource_type', op: 'eq', value: state.resourceType },
  ];

  for (const facet of visibleFacets) {
    if (facet.uiOnly) continue;
    const value = state.facets[facet.id];
    if (!value) continue;
    filters.push(...compileFacetFilter(facet, value));
  }

  const aggs = visibleFacets
    .filter((facet) => facet.widget !== 'range' && !facet.uiOnly)
    .map((facet) => facet.field);

  const request: SearchRequest = {
    query: state.query || null,
    filters,
    aggs,
    sort: { field: state.sortField, order: state.sortOrder },
    offset: state.offset,
    limit: state.limit,
  };

  return request;
}

function compileFacetFilter(
  facet: FacetConfig,
  value: FacetValue
): SearchFilter[] {
  const { field } = facet;
  switch (value.kind) {
    case 'terms': {
      if (value.values.length === 0) return [];
      const op = facet.termsOp ?? 'overlap';
      return [{ field, op, value: value.values }];
    }
    case 'toggle': {
      if (!value.value) return [];
      return [{ field, op: 'eq', value: true }];
    }
    case 'range': {
      const out: SearchFilter[] = [];
      if (value.from) out.push({ field, op: 'gte', value: value.from });
      if (value.to) out.push({ field, op: 'lte', value: value.to });
      return out;
    }
  }
}
