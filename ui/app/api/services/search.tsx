import { parseDate } from '@internationalized/date';
import mockModelsData from '~/api/mocks/results-mock-data.json';
import mockDatasetsData from '~/api/mocks/datasets-mock-data.json';
import type { ReactNode } from 'react';
import {
  CalendarIcon,
  Square3Stack3DIcon,
  VariableIcon,
} from '@heroicons/react/16/solid';
import { CommandLineIcon, DocumentIcon } from '@heroicons/react/24/solid';

// ====================
// Shared types
// ====================

interface Affiliation {
  institution: string;
  department?: string;
}

interface Author {
  name: string;
  orcid?: string;
  affiliation?: Affiliation;
}

interface Tag {
  category: string;
  value: string;
}

/** Fields shared by every result type */
interface BaseResult {
  id: string;
  doi?: string;
  title: string;
  description: string;
  authors: Author[];
  published_date: string;
  updated_date: string;
  version?: string;
  citations?: number;
  featured?: boolean;
  scales: string[];
  tags?: Tag[];
}

// ====================
// Model results
// ====================

export interface ModelResult extends BaseResult {
  executable: boolean;
  types?: string[];
  programming_languages?: string[];
}

// ====================
// Dataset results
// ====================

export interface DatasetResult extends BaseResult {
  formats?: string[];
  size_bytes?: number;
  record_count?: number;
}

// ====================
// Result type
// ====================

export type ResultType = 'models' | 'datasets';

// ====================
// Sort order
// ====================

export type SortOrder = 'relevance' | 'latest' | 'featured';

// ====================
// Filter values
// ====================

/** Value for a switch filter */
export interface SwitchFilterValue {
  type: 'switch';
  value: boolean;
}

/** Value for a checkbox/multi-select filter */
export interface CheckboxFilterValue {
  type: 'checkbox';
  selected: string[];
}

/** Value for a date-range filter */
export interface DateRangeFilterValue {
  type: 'date_range';
  start?: string; // ISO date string
  end?: string; // ISO date string
}

/** A filter value is a switch, a set of selected terms, or a date range. */
export type FilterValue =
  | SwitchFilterValue
  | CheckboxFilterValue
  | DateRangeFilterValue;

// ====================
// Filter configuration
// ====================

interface BaseConfig {
  id: string;
  label: string;
  icon: ReactNode;
}

export interface SwitchConfig extends BaseConfig {
  type: 'switch';
  /** URL param name used to persist this filter */
  param: string;
}

export interface CheckboxConfig extends BaseConfig {
  type: 'checkbox';
  /** URL param name used to persist this filter */
  param: string;
}

export interface DateRangeConfig extends BaseConfig {
  type: 'date_range';
  /** URL param names used to persist start/end */
  startParam: string;
  endParam: string;
  bounds: { min: string; max: string };
}

export type FilterConfig = SwitchConfig | CheckboxConfig | DateRangeConfig;

export const MODEL_FILTER_CONFIGS: FilterConfig[] = [
  {
    id: 'executable',
    type: 'switch',
    label: 'Executable',
    param: 'executable',
    icon: <CommandLineIcon className="size-5" />,
  },
  {
    id: 'scales',
    type: 'checkbox',
    label: 'Model Scales',
    param: 'scale',
    icon: <Square3Stack3DIcon className="size-5" />,
  },
  {
    id: 'types',
    type: 'checkbox',
    label: 'Model Types',
    param: 'type',
    icon: <VariableIcon className="size-5" />,
  },
  {
    id: 'publication_date',
    type: 'date_range',
    label: 'Publication Date',
    startParam: 'pub_start',
    endParam: 'pub_end',
    bounds: { min: '1970-01-01', max: new Date().toISOString().split('T')[0] },
    icon: <CalendarIcon className="size-5" />,
  },
];

export const DATASET_FILTER_CONFIGS: FilterConfig[] = [
  {
    id: 'scales',
    type: 'checkbox',
    label: 'Scales',
    param: 'scale',
    icon: <Square3Stack3DIcon className="size-5" />,
  },
  {
    id: 'formats',
    type: 'checkbox',
    label: 'Formats',
    param: 'format',
    icon: <DocumentIcon className="size-5" />,
  },
  {
    id: 'publication_date',
    type: 'date_range',
    label: 'Publication Date',
    startParam: 'pub_start',
    endParam: 'pub_end',
    bounds: { min: '1970-01-01', max: new Date().toISOString().split('T')[0] },
    icon: <CalendarIcon className="size-5" />,
  },
];

/** Returns the correct filter configs for a given result type */
export function getFilterConfigs(resultType: ResultType): FilterConfig[] {
  return resultType === 'models'
    ? MODEL_FILTER_CONFIGS
    : DATASET_FILTER_CONFIGS;
}

// ====================
// Aggregations
// ====================

export type TermAggregation = Record<string, number>;
export type StatsAggregation = { min: string | null; max: string | null };

export interface SearchAggregations {
  [key: string]: TermAggregation | StatsAggregation;
}

// ====================
// Pagination
// ====================

export interface PaginationMeta {
  offset: number;
  limit: number;
  total: number;
}

// ====================
// Search query & response
// ====================

export interface SearchQuery {
  query?: string;
  resultType: ResultType;
  sort: SortOrder;
  filters: Record<string, FilterValue>;
  offset?: number;
  limit?: number;
}

export interface SearchResponse {
  results: ModelResult[] | DatasetResult[];
  pagination: PaginationMeta;
  aggregations: SearchAggregations;
}

// ====================
// Mock data
// ====================

const MOCK_MODELS = mockModelsData as ModelResult[];
const MOCK_DATASETS = mockDatasetsData as DatasetResult[];

// ====================
// Field extraction helpers
// ====================

function getModelFieldValues(result: ModelResult, fieldId: string): string[] {
  switch (fieldId) {
    case 'scales': {
      return result.scales ?? [];
    }
    case 'types': {
      return result.types ?? [];
    }
    default: {
      return [];
    }
  }
}

function getDatasetFieldValues(
  result: DatasetResult,
  fieldId: string
): string[] {
  switch (fieldId) {
    case 'scales': {
      return result.scales ?? [];
    }
    case 'formats': {
      return result.formats ?? [];
    }
    default: {
      return [];
    }
  }
}

function getFieldValues(
  result: BaseResult,
  fieldId: string,
  resultType: ResultType
): string[] {
  if (resultType === 'models')
    return getModelFieldValues(result as ModelResult, fieldId);
  return getDatasetFieldValues(result as DatasetResult, fieldId);
}

// ====================
// Term aggregation
// ====================

function computeTermAggregation(
  results: BaseResult[],
  fieldId: string,
  resultType: ResultType
): TermAggregation {
  const counts: Record<string, number> = {};
  for (const result of results) {
    for (const value of getFieldValues(result, fieldId, resultType)) {
      counts[value] = (counts[value] || 0) + 1;
    }
  }
  return counts;
}

// ====================
// Filtering logic
// ====================

function applyFilters<T extends BaseResult>(
  items: T[],
  filters: Record<string, FilterValue>,
  filterConfigs: FilterConfig[],
  resultType: ResultType
): T[] {
  return items.filter((result) => {
    for (const config of filterConfigs) {
      const filterValue = filters[config.id];
      if (!filterValue) continue;

      if (config.type === 'switch' && filterValue.type === 'switch') {
        if (filterValue.value) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const field = (result as any)[config.id];
          if (field !== true) return false;
        }
      } else if (
        config.type === 'checkbox' &&
        filterValue.type === 'checkbox'
      ) {
        if (filterValue.selected.length > 0) {
          const resultValues = getFieldValues(result, config.id, resultType);
          if (!resultValues.some((v) => filterValue.selected.includes(v))) {
            return false;
          }
        }
      } else if (
        config.type === 'date_range' &&
        filterValue.type === 'date_range' &&
        (filterValue.start || filterValue.end)
      ) {
        const pubDate = parseDate(result.published_date);
        if (
          filterValue.start &&
          pubDate.compare(parseDate(filterValue.start)) < 0
        )
          return false;
        if (filterValue.end && pubDate.compare(parseDate(filterValue.end)) > 0)
          return false;
      }
    }
    return true;
  });
}

// ====================
// Sorting logic
// ====================

function applySorting<T extends BaseResult>(items: T[], sort: SortOrder): T[] {
  const sorted = [...items];
  switch (sort) {
    case 'latest': {
      sorted.sort(
        (a, b) =>
          new Date(b.published_date).getTime() -
          new Date(a.published_date).getTime()
      );
      break;
    }
    case 'featured': {
      sorted.sort((a, b) => {
        // Featured items first, then by published date
        if (a.featured && !b.featured) return -1;
        if (!a.featured && b.featured) return 1;
        return (
          new Date(b.published_date).getTime() -
          new Date(a.published_date).getTime()
        );
      });
      break;
    }
    default: {
      // In mock mode, relevance is just original order (no-op).
      // A real API would score by query relevance.
      break;
    }
  }
  return sorted;
}

// ====================
// Text search (mock)
// ====================

// function applyTextSearch<T extends BaseResult>(
//   items: T[],
//   query: string | undefined
// ): T[] {
//   if (!query) return items;
//   const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
//   return items.filter((item) => {
//     const searchable = [
//       item.title,
//       item.description,
//       ...item.authors.map((a) => a.name),
//       ...(item.tags?.map((t) => t.value) ?? []),
//       ...item.scales,
//     ]
//       .join(' ')
//       .toLowerCase();
//     return terms.some((term) => searchable.includes(term));
//   });
// }

// ====================
// Main search function
// ====================

export async function fetchSearchResults(
  searchQuery: SearchQuery
): Promise<SearchResponse> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 750));

  const {
    // query,
    resultType,
    sort,
    filters,
    offset = 0,
    limit = 20,
  } = searchQuery;

  const filterConfigs = getFilterConfigs(resultType);

  // Run the pipeline with the concrete type so generics narrow correctly
  function runPipeline<T extends BaseResult>(
    source: T[]
  ): {
    sorted: T[];
    textMatched: T[];
    filtered: T[];
  } {
    // const textMatched = applyTextSearch(source, query);
    const textMatched = source; // just return all results for now.
    const filtered = applyFilters(
      textMatched,
      filters,
      filterConfigs,
      resultType
    );
    const sorted = applySorting(filtered, sort);
    return { sorted, textMatched, filtered };
  }

  const { sorted, textMatched, filtered } =
    resultType === 'models'
      ? runPipeline(MOCK_MODELS)
      : runPipeline(MOCK_DATASETS);

  // Build aggregations - term aggregations run against all text-matched
  // results (before filter narrowing) so facet counts reflect the query scope.
  const aggregations: SearchAggregations = {};
  for (const config of filterConfigs) {
    switch (config.type) {
      case 'switch': {
        let trueCount = 0;
        for (const result of textMatched) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          if ((result as any)[config.id] === true) trueCount++;
        }
        aggregations[config.id] = {
          true: trueCount,
          false: textMatched.length - trueCount,
        };

        break;
      }
      case 'checkbox': {
        aggregations[config.id] = computeTermAggregation(
          textMatched,
          config.id,
          resultType
        );

        break;
      }
      case 'date_range': {
        let minDate: string | null = null;
        let maxDate: string | null = null;
        for (const result of filtered) {
          if (result.published_date) {
            if (!minDate || result.published_date < minDate)
              minDate = result.published_date;
            if (!maxDate || result.published_date > maxDate)
              maxDate = result.published_date;
          }
        }
        aggregations[config.id] = { min: minDate, max: maxDate };

        break;
      }
      // No default
    }
  }

  // Paginate
  const paginatedResults = sorted.slice(offset, offset + limit);

  return {
    results: paginatedResults,
    pagination: { offset, limit, total: sorted.length },
    aggregations,
  };
}
