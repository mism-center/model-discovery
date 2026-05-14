import { QueryClient } from '@tanstack/react-query';

/**
 * - `staleTime: 30s` — search results and facet counts don't need to
 *    refetch on every component mount.
 * - `retry: 1` — be forgiving of transient network hiccups but don't
 *    silently spam the API on real failures.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
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
