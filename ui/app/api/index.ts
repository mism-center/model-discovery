export { apiClient } from './client/client';
export { ApiError } from './client/errors';

export {
  searchResources,
  type SearchRequest,
  type SearchResponse,
  type SearchFilter,
  type SearchSort,
  type SearchResultItem,
  type AggResult,
  type AggBucket,
  type Author,
  type Publication,
} from './endpoints/search';
