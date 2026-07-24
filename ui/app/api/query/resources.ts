import { queryOptions } from '@tanstack/react-query';

import {
  fetchResourceFileText,
  listResourceFiles,
  type ResourceFilesResponse,
} from '~/api/endpoints/resources';

export const resourceKeys = {
  all: ['resources'] as const,
  files: (resourceId: string) =>
    [...resourceKeys.all, 'files', resourceId] as const,
  fileText: (resourceId: string, file: string) =>
    [...resourceKeys.all, 'file-text', resourceId, file] as const,
};

export function resourceFilesQueryOptions(resourceId: string) {
  return queryOptions<ResourceFilesResponse>({
    queryKey: resourceKeys.files(resourceId),
    queryFn: ({ signal }) => listResourceFiles(resourceId, { signal }),
  });
}

export function resourceFileTextQueryOptions(resourceId: string, file: string) {
  return queryOptions<string>({
    queryKey: resourceKeys.fileText(resourceId, file),
    queryFn: ({ signal }) =>
      fetchResourceFileText(resourceId, file, { signal }),
    // A run's output files are immutable, so cache the content generously.
    staleTime: 5 * 60 * 1000,
  });
}
