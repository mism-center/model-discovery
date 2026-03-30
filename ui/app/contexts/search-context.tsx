import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';
import { useSearchParams } from 'react-router';
import { useSearchQuery } from '../api/hooks/use-search';
import {
  getFilterConfigs,
  type DatasetResult,
  type FilterConfig,
  type FilterValue,
  type ModelResult,
  type PaginationMeta,
  type ResultType,
  type SearchAggregations,
  type SearchQuery,
  type SortOrder,
} from '../api/services/search';

// ============================================================================
// Context types
// ============================================================================

interface ResultSet<T> {
  results: T[] | null;
  pagination: PaginationMeta | null;
  aggregations: SearchAggregations | null;
  isLoading: boolean;
  error: Error | null;
}

interface SearchContextType {
  // Config & state
  filterConfigs: FilterConfig[];
  searchQuery: string;
  resultType: ResultType;
  sort: SortOrder;
  isCompact: boolean;
  hasActiveFilters: boolean;

  // Both result sets, always available
  models: ResultSet<ModelResult>;
  datasets: ResultSet<DatasetResult>;

  // Unified filter accessors (keyed by filter id)
  getFilterValue: (filterId: string) => FilterValue | undefined;
  setFilterValue: (filterId: string, value: FilterValue) => void;

  // Actions
  doSearch: (query: string) => void;
  setResultType: (resultType: ResultType) => void;
  setSort: (sort: SortOrder) => void;
  setPage: (newOffset: number) => void;
  clearFilter: (filterId: string) => void;
  clearAllFilters: () => void;
}

const SearchContext = createContext<SearchContextType | null>(null);

// ============================================================================
// Helpers: URL <-> FilterValue translation
// ============================================================================

function filtersFromParams(
  searchParams: URLSearchParams,
  filterConfigs: FilterConfig[]
): Record<string, FilterValue> {
  const filters: Record<string, FilterValue> = {};
  for (const config of filterConfigs) {
    switch (config.type) {
      case 'switch': {
        const raw = searchParams.get(config.param);
        if (raw === 'true') {
          filters[config.id] = { type: 'switch', value: true };
        }
        break;
      }
      case 'checkbox': {
        const selected = searchParams.getAll(config.param);
        if (selected.length > 0) {
          filters[config.id] = { type: 'checkbox', selected };
        }
        break;
      }
      case 'date_range': {
        const start = searchParams.get(config.startParam) ?? undefined;
        const end = searchParams.get(config.endParam) ?? undefined;
        if (start || end) {
          filters[config.id] = { type: 'date_range', start, end };
        }
        break;
      }
    }
  }
  return filters;
}

function filterToParams(
  config: FilterConfig,
  value: FilterValue,
  params: URLSearchParams
): void {
  switch (config.type) {
    case 'switch': {
      if (value.type === 'switch') {
        if (value.value) {
          params.set(config.param, 'true');
        } else {
          params.delete(config.param);
        }
      }
      break;
    }
    case 'checkbox': {
      if (value.type === 'checkbox') {
        params.delete(config.param);
        for (const v of value.selected) {
          params.append(config.param, v);
        }
      }
      break;
    }
    case 'date_range': {
      if (value.type === 'date_range') {
        params.delete(config.startParam);
        params.delete(config.endParam);
        if (value.start) params.set(config.startParam, value.start);
        if (value.end) params.set(config.endParam, value.end);
      }
      break;
    }
  }
}

function clearFilterParams(
  config: FilterConfig,
  params: URLSearchParams
): void {
  switch (config.type) {
    case 'switch':
    case 'checkbox': {
      params.delete(config.param);
      break;
    }
    case 'date_range': {
      params.delete(config.startParam);
      params.delete(config.endParam);
      break;
    }
  }
}

/** Remove all filter-related params (when switching result type, filters reset) */
function clearAllFilterParams(
  filterConfigs: FilterConfig[],
  params: URLSearchParams
): void {
  for (const config of filterConfigs) {
    clearFilterParams(config, params);
  }
}

// ============================================================================
// Constants
// ============================================================================

const VALID_RESULT_TYPES = new Set<ResultType>(['models', 'datasets']);
const VALID_SORTS = new Set<SortOrder>(['relevance', 'latest', 'featured']);

function parseResultType(raw: string | null): ResultType {
  if (raw && VALID_RESULT_TYPES.has(raw as ResultType))
    return raw as ResultType;
  return 'models';
}

function parseSortOrder(raw: string | null): SortOrder {
  if (raw && VALID_SORTS.has(raw as SortOrder)) return raw as SortOrder;
  return 'relevance';
}

// ============================================================================
// Provider
// ============================================================================

export function SearchProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Derive top-level state from URL params
  const searchQuery = searchParams.get('q') ?? '';
  const resultType = parseResultType(searchParams.get('result_type'));
  const sort = parseSortOrder(searchParams.get('sort'));
  const isCompact = !!searchQuery;

  // Filter configs depend on the active result type (for the sidebar)
  const filterConfigs = useMemo(
    () => getFilterConfigs(resultType),
    [resultType]
  );

  const filters = useMemo(
    () => filtersFromParams(searchParams, filterConfigs),
    [searchParams, filterConfigs]
  );

  const hasActiveFilters = useMemo(
    () => Object.keys(filters).length > 0,
    [filters]
  );

  // When no query is active (home view), always use featured sort.
  const effectiveSort = searchQuery ? sort : 'featured';

  // Derive offset/limit as stable primitives
  const offset =
    Number.parseInt(searchParams.get('offset') ?? '0', 10) || undefined;
  const limit = Number.parseInt(searchParams.get('limit') ?? '5', 10);

  // Build queries for both result types in parallel.
  // Filters only apply to the active tab's result type since configs differ.
  const modelsQuery = useMemo<SearchQuery>(
    () => ({
      query: searchQuery || undefined,
      resultType: 'models',
      sort: effectiveSort,
      filters: resultType === 'models' ? filters : {},
      offset: resultType === 'models' ? offset : undefined,
      limit,
    }),
    [searchQuery, effectiveSort, filters, resultType, offset, limit]
  );

  const datasetsQuery = useMemo<SearchQuery>(
    () => ({
      query: searchQuery || undefined,
      resultType: 'datasets',
      sort: effectiveSort,
      filters: resultType === 'datasets' ? filters : {},
      offset: resultType === 'datasets' ? offset : undefined,
      limit,
    }),
    [searchQuery, effectiveSort, filters, resultType, offset, limit]
  );

  const {
    data: modelsData,
    isLoading: modelsLoading,
    error: modelsError,
  } = useSearchQuery(modelsQuery);

  const {
    data: datasetsData,
    isLoading: datasetsLoading,
    error: datasetsError,
  } = useSearchQuery(datasetsQuery);

  const models = useMemo<ResultSet<ModelResult>>(
    () => ({
      results: (modelsData?.results as ModelResult[]) ?? null,
      pagination: modelsData?.pagination ?? null,
      aggregations: modelsData?.aggregations ?? null,
      isLoading: modelsLoading,
      error: modelsError,
    }),
    [modelsData, modelsLoading, modelsError]
  );

  const datasets = useMemo<ResultSet<DatasetResult>>(
    () => ({
      results: (datasetsData?.results as DatasetResult[]) ?? null,
      pagination: datasetsData?.pagination ?? null,
      aggregations: datasetsData?.aggregations ?? null,
      isLoading: datasetsLoading,
      error: datasetsError,
    }),
    [datasetsData, datasetsLoading, datasetsError]
  );

  // Clamp offset: if it exceeds the total results for the active tab,
  // reset to the last valid page.
  const activeTotal =
    resultType === 'models'
      ? models.pagination?.total
      : datasets.pagination?.total;

  useEffect(() => {
    if (activeTotal === undefined || !offset) return;
    if (offset >= activeTotal) {
      const lastPageOffset =
        activeTotal > 0 ? Math.floor((activeTotal - 1) / limit) * limit : 0;
      const params = new URLSearchParams(searchParams);
      if (lastPageOffset > 0) {
        params.set('offset', lastPageOffset.toString());
      } else {
        params.delete('offset');
      }
      setSearchParams(params, { preventScrollReset: true, replace: true });
    }
  }, [activeTotal, offset, limit, searchParams, setSearchParams]);

  // Unified getter
  const getFilterValue = useCallback(
    (filterId: string): FilterValue | undefined => filters[filterId],
    [filters]
  );

  // Unified setter
  const setFilterValue = useCallback(
    (filterId: string, value: FilterValue) => {
      const config = filterConfigs.find((c) => c.id === filterId);
      if (!config) return;

      const params = new URLSearchParams(searchParams);
      params.delete('offset');
      filterToParams(config, value, params);
      setSearchParams(params, { preventScrollReset: true });
    },
    [searchParams, setSearchParams, filterConfigs]
  );

  // Actions
  const doSearch = useCallback(
    (q: string) => {
      const params = new URLSearchParams();
      if (q) params.set('q', q);
      setSearchParams(params);
    },
    [setSearchParams]
  );

  const setResultType = useCallback(
    (newResultType: ResultType) => {
      const params = new URLSearchParams(searchParams);
      // Clear filters since they differ between result types
      clearAllFilterParams(filterConfigs, params);
      params.delete('offset');
      if (newResultType === 'models') {
        params.delete('result_type');
      } else {
        params.set('result_type', newResultType);
      }
      setSearchParams(params, {
        preventScrollReset: true,
        replace: true,
      });
    },
    [searchParams, setSearchParams, filterConfigs]
  );

  const setSort = useCallback(
    (newSort: SortOrder) => {
      const params = new URLSearchParams(searchParams);
      params.delete('offset');
      if (newSort === 'relevance') {
        params.delete('sort');
      } else {
        params.set('sort', newSort);
      }
      setSearchParams(params, { preventScrollReset: true });
    },
    [searchParams, setSearchParams]
  );

  const setPage = useCallback(
    (newOffset: number) => {
      const params = new URLSearchParams(searchParams);
      if (newOffset > 0) {
        params.set('offset', newOffset.toString());
      } else {
        params.delete('offset');
      }
      setSearchParams(params);
    },
    [searchParams, setSearchParams]
  );

  const clearFilter = useCallback(
    (filterId: string) => {
      const config = filterConfigs.find((c) => c.id === filterId);
      if (!config) return;

      const params = new URLSearchParams(searchParams);
      params.delete('offset');
      clearFilterParams(config, params);
      setSearchParams(params, { preventScrollReset: true });
    },
    [searchParams, setSearchParams, filterConfigs]
  );

  const clearAllFilters = useCallback(() => {
    const params = new URLSearchParams();
    if (searchQuery) params.set('q', searchQuery);
    if (resultType !== 'models') params.set('result_type', resultType);
    if (sort !== 'relevance') params.set('sort', sort);
    setSearchParams(params, { preventScrollReset: true });
  }, [searchQuery, resultType, sort, setSearchParams]);

  const value = useMemo<SearchContextType>(
    () => ({
      filterConfigs,
      searchQuery,
      resultType,
      sort,
      isCompact,
      hasActiveFilters,
      models,
      datasets,
      getFilterValue,
      setFilterValue,
      doSearch,
      setResultType,
      setSort,
      setPage,
      clearFilter,
      clearAllFilters,
    }),
    [
      filterConfigs,
      searchQuery,
      resultType,
      sort,
      isCompact,
      hasActiveFilters,
      models,
      datasets,
      getFilterValue,
      setFilterValue,
      doSearch,
      setResultType,
      setSort,
      setPage,
      clearFilter,
      clearAllFilters,
    ]
  );

  return (
    <SearchContext.Provider value={value}>{children}</SearchContext.Provider>
  );
}

// ============================================================================
// Hook
// ============================================================================

export function useSearch(): SearchContextType {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error('useSearch must be used within a SearchProvider');
  }
  return context;
}
