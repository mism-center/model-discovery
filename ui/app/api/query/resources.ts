import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
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

/**
 * A resource's file listing (`GET /resources/{id}/files`).
 *
 * `client` lets an SSR loader pass a cookie-forwarding `serverApiClient`,
 * matching `modelDetailQueryOptions`. A loader prefetch that omits it runs
 * against the browser client — wrong base URL on Node, no cookie forwarding — so
 * the query fails on the server, `dehydrate()` drops it, and the browser
 * refetches from scratch.
 *
 * The model detail loader prefetches this for *document* requests only. It is by
 * far the slowest call that page makes (~440ms against dev), so awaiting it on
 * client-side navigations blocked transition to the page until a low-prio section loaded.
 * On that path `FilesSection` fetches it on mount and shows a skeleton instead.
 */
export function resourceFilesQueryOptions(
  resourceId: string,
  client?: Client<paths>
) {
  return queryOptions<ResourceFilesResponse>({
    queryKey: resourceKeys.files(resourceId),
    queryFn: ({ signal }) => listResourceFiles(resourceId, { signal, client }),
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
