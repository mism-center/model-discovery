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

export {
  executeModelRun,
  listModelRuns,
  getRun,
  cancelRun,
  pickActiveRun,
  isTerminalStatus,
  TERMINAL_RUN_STATUSES,
  type ExecuteRunRequest,
  type ExecuteRunResponse,
  type ModelRunDetailsResponse,
  type ModelRunDetailItem,
  type RunDetailResponse,
  type RunDetailItem,
  type RunStatus,
  type ResourceSummaryItem,
} from './endpoints/runs';

export {
  listResourceFiles,
  resourceDownloadUrl,
  type ResourceFileItem,
  type ResourceFilesResponse,
} from './endpoints/resources';
