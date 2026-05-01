import { queryOptions } from '@tanstack/react-query';

import {
  listResourceFiles,
  type ResourceFilesResponse,
} from '~/api/endpoints/resources';

export const resourceKeys = {
  all: ['resources'] as const,
  files: (resourceId: string) =>
    [...resourceKeys.all, 'files', resourceId] as const,
};

export function resourceFilesQueryOptions(resourceId: string) {
  return queryOptions<ResourceFilesResponse>({
    queryKey: resourceKeys.files(resourceId),
    queryFn: ({ signal }) => listResourceFiles(resourceId, { signal }),
  });
}
