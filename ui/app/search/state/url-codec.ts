import { FACETS } from './facets.config';
import {
  DEFAULT_LIMIT,
  DEFAULT_SEARCH_STATE,
  type FacetValue,
  type FacetWidget,
  type ResourceType,
  type SearchState,
  type SortField,
  type SortOrder,
} from './types';

/**
 * URL <-> SearchState codec.
 *
 * The URL is the source of truth for search state. This module is the only
 * place that knows how each field is spelled in query params.
 *
 * Param layout:
 *   q               — full-text query
 *   type            — resource_type tab (model | dataset)
 *   sort            — sort field (_score | name | created_at | updated_at)
 *   order           — sort order (asc | desc)
 *   offset, limit   — pagination
 *   <facetId>       — terms facet, repeated: ?model_scales=A&model_scales=B
 *   <facetId>       — toggle facet, single: ?<facetId>=true (absent = false)
 *   <facetId>_from  — range facet lower bound
 *   <facetId>_to    — range facet upper bound
 *
 * Facet param names are the facet id, which by convention equals the API
 * field name.
 */

const RESERVED_PARAMS = new Set([
  'q',
  'type',
  'sort',
  'order',
  'offset',
  'limit',
]);

export function searchStateFromParams(params: URLSearchParams): SearchState {
  const query = params.get('q') ?? DEFAULT_SEARCH_STATE.query;
  const resourceType = parseResourceType(params.get('type'));
  const sortField = parseSortField(params.get('sort'));
  const sortOrder = parseSortOrder(params.get('order'));
  const offset = parseNonNegativeInt(params.get('offset'), 0);
  const limit = parseNonNegativeInt(params.get('limit'), DEFAULT_LIMIT);

  const facets: Record<string, FacetValue> = {};
  for (const facet of FACETS) {
    const value = readFacetFromParams(facet.id, facet.widget, params);
    if (value) facets[facet.id] = value;
  }

  return {
    query,
    resourceType,
    facets,
    sortField,
    sortOrder,
    offset,
    limit,
  };
}

export function searchStateToParams(state: SearchState): URLSearchParams {
  const params = new URLSearchParams();

  if (state.query) params.set('q', state.query);
  if (state.resourceType !== DEFAULT_SEARCH_STATE.resourceType) {
    params.set('type', state.resourceType);
  }
  if (state.sortField !== DEFAULT_SEARCH_STATE.sortField) {
    params.set('sort', state.sortField);
  }
  if (state.sortOrder !== DEFAULT_SEARCH_STATE.sortOrder) {
    params.set('order', state.sortOrder);
  }
  if (state.offset !== 0) params.set('offset', String(state.offset));
  if (state.limit !== DEFAULT_LIMIT) params.set('limit', String(state.limit));

  for (const [id, value] of Object.entries(state.facets)) {
    writeFacetToParams(id, value, params);
  }

  return params;
}

/**
 * Remove all params for a given facet.
 * Mutates and returns a clone of the input params.
 */
export function removeFacetParams(
  id: string,
  params: URLSearchParams
): URLSearchParams {
  const copy = new URLSearchParams(params);
  copy.delete(id);
  copy.delete(`${id}_from`);
  copy.delete(`${id}_to`);
  return copy;
}

/** Remove every facet-shaped param. Leaves reserved keys (q, type, sort, ...) intact. */
export function removeAllFacetParams(params: URLSearchParams): URLSearchParams {
  const copy = new URLSearchParams(params);
  const keysToDelete: string[] = [];
  for (const key of copy.keys()) {
    if (RESERVED_PARAMS.has(key)) continue;
    // All other keys are assumed to belong to facets (facet id, facetid_from, facetid_to).
    keysToDelete.push(key);
  }
  for (const key of keysToDelete) copy.delete(key);
  return copy;
}

// ---------- helpers ----------

function parseResourceType(value: string | null): ResourceType {
  return value === 'dataset' ? 'dataset' : 'model';
}

function parseSortField(value: string | null): SortField {
  switch (value) {
    case 'name':
    case 'created_at':
    case 'updated_at':
    case '_score': {
      return value;
    }
    default: {
      return DEFAULT_SEARCH_STATE.sortField;
    }
  }
}

function parseSortOrder(value: string | null): SortOrder {
  return value === 'asc' ? 'asc' : 'desc';
}

function parseNonNegativeInt(value: string | null, fallback: number): number {
  if (value === null) return fallback;
  const n = Number.parseInt(value, 10);
  if (!Number.isFinite(n) || n < 0) return fallback;
  return n;
}

function readFacetFromParams(
  id: string,
  widget: FacetWidget,
  params: URLSearchParams
): FacetValue | undefined {
  switch (widget) {
    case 'terms': {
      const values = params.getAll(id).filter((v) => v.length > 0);
      if (values.length === 0) return;
      return { kind: 'terms', values };
    }
    case 'toggle': {
      const raw = params.get(id);
      if (raw !== 'true') return;
      return { kind: 'toggle', value: true };
    }
    case 'range': {
      const from = params.get(`${id}_from`) ?? undefined;
      const to = params.get(`${id}_to`) ?? undefined;
      if (!from && !to) return;
      return { kind: 'range', from: from || undefined, to: to || undefined };
    }
    default: {
      return;
    }
  }
}

function writeFacetToParams(
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
