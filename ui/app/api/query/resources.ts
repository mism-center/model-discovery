import { queryOptions } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import {
  listResourceFiles,
  type ResourceFilesResponse,
} from '~/api/endpoints/resources';

export const resourceKeys = {
  all: ['resources'] as const,
  files: (resourceId: string) =>
    [...resourceKeys.all, 'files', resourceId] as const,
};

/**
 * A resource's file listing (`GET /resources/{id}/files`).
 *
 * `client` lets SSR loaders pass a cookie-forwarding `serverApiClient`, matching
 * `modelDetailQueryOptions`. Without it a loader prefetch runs against the
 * browser client — wrong base URL on Node, no cookie forwarding — so the query
 * fails on the server, `dehydrate()` drops it, and the browser refetches from
 * scratch. That is why this section used to arrive unhydrated.
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
