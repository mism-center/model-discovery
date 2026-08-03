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
} from './endpoints/search';

export { type Author, type Publication } from './types';

export {
  executeModelRun,
  listModelRuns,
  getRun,
  cancelRun,
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
  getModel,
  type RegisterModelResponse,
  type EntryPointDTO,
  type ArgumentDTO,
} from './endpoints/models';

export {
  listResourceFiles,
  resourceDownloadUrl,
  fetchResourceFileText,
  TEXT_PREVIEW_MAX_BYTES,
  type ResourceFileItem,
  type ResourceFilesResponse,
} from './endpoints/resources';
