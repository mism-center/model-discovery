import { QueryCache, QueryClient } from '@tanstack/react-query';

import { ApiError } from '~/api/client/errors';

/**
 * - `staleTime: 30s` — search results and facet counts don't need to
 *    refetch on every component mount.
 * - `retry: 1` — be forgiving of transient network hiccups but don't
 *    silently spam the API on real failures.
 * - On any auth failure (401/403) from a non-auth query, drop the cached
 *    user to `null` and capabilities to all-false so the UI flips to a
 *    signed-out state. Both auth queries already resolve those same values
 *    on 401 themselves (`fetchUser`, `fetchCapabilities`), so the
 *    `query.queryKey[0] !== 'auth'` guard avoids a no-op self-loop.
 */
export function createQueryClient(): QueryClient {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (
          error instanceof ApiError &&
          error.isAuthError &&
          query.queryKey[0] !== 'auth'
        ) {
          // Inlined to avoid a circular import with ~/api/auth/user and
          // ~/api/auth/capabilities.
          client.setQueryData(['auth', 'me'], null);
          client.setQueryData(['auth', 'capabilities'], {
            uploader: false,
            upload_reviewer: false,
            image_checker: false,
            executor: false,
          });
        }
      },
    }),
  });
  return client;
}

/**
 * SSR-safe accessor.
 *   - On the server, return a fresh client per call so requests never share
 *     cache across users.
 *   - In the browser, cache a module-level singleton so navigations reuse
 *     the cache populated by the route loader.
 */
let browserClient: QueryClient | undefined;

export function getQueryClient(): QueryClient {
  if (globalThis.window === undefined) {
    return createQueryClient();
  }
  if (!browserClient) {
    browserClient = createQueryClient();
  }
  return browserClient;
}
