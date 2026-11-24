export type ResourceType = 'model' | 'dataset';

/**
 * Widget type, which determines both the UI rendering and the operator we
 * translate to when building the API request. Mirrors the 3 shapes of
 * `SearchFilterDTO.value` we actually need:
 *
 *   - `terms`    → array-valued, compiled to `overlap` (any match).
 *   - `toggle`   → boolean, compiled to `eq` (only sent when true).
 *   - `range`    → {from, to}, compiled to a `gte` + `lte` pair on the same field.
 */
export type FacetWidget = 'terms' | 'toggle' | 'range';

export type FacetValue =
  | { kind: 'terms'; values: string[] }
  | { kind: 'toggle'; value: boolean }
  | { kind: 'range'; from?: string; to?: string };

export type SortField = '_score' | 'name' | 'created_at' | 'updated_at';
export type SortOrder = 'asc' | 'desc';

export interface SearchState {
  /** Full-text query. */
  query: string;
  /** Which tab is active. Compiled to a resource_type eq filter. */
  resourceType: ResourceType;
  facets: Record<string, FacetValue>;
  sortField: SortField;
  sortOrder: SortOrder;
  offset: number;
  limit: number;
}

export const DEFAULT_LIMIT = 25;

export const DEFAULT_SEARCH_STATE: SearchState = {
  query: '',
  resourceType: 'model',
  facets: {},
  sortField: '_score',
  sortOrder: 'desc',
  offset: 0,
  limit: DEFAULT_LIMIT,
};
