import { useQuery, type QueryClient } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';
import { ApiError } from '~/api/client/errors';
import { getQueryClient } from '~/api/query/query-client';

export type CurrentUser = components['schemas']['CurrentUser'];

export const userQueryKey = ['auth', 'me'] as const;

type ApiClientType = Client<paths>;

/**
 * Fetch the current user. 401 from the API means "not signed in", which is
 * a normal state — return null rather than throwing. Other failures
 * propagate so the query lands in an error state and the UI can surface it.
 */
export async function fetchUser(
  client: ApiClientType = apiClient
): Promise<CurrentUser | null> {
  try {
    const { data } = await client.GET('/api/auth/me');
    return data ?? null;
  } catch (error) {
    if (error instanceof ApiError && error.isAuthError) return null;
    throw error;
  }
}

// Pathname -> server route key (mirrors ROUTE_PATHS in the API's return_to
// allowlist).
const RETURN_TO_KEYS: Record<string, string> = {
  '/search': 'search',
};

/**
 * Trigger an OIDC login. Top-level navigation so the browser follows the
 * 302 chain to the IdP and back through `/api/auth/callback` cleanly. Sends
 * the current route key + query so the callback can return the user here.
 */
export function signIn(): void {
  const key = RETURN_TO_KEYS[globalThis.location.pathname];
  const params = new URLSearchParams();
  if (key) {
    params.set('return_to_key', key);
    const query = globalThis.location.search.replace(/^\?/, '');
    if (query) params.set('return_to_query', query);
  }
  const qs = params.toString();
  globalThis.location.assign(`/api/auth/login${qs ? `?${qs}` : ''}`);
}

/**
 * Clear the local session and, if the IdP supports RP-initiated logout,
 * navigate top-level to its `end_session_endpoint` so the IdP can clear
 * its own session. Otherwise land on `/`.
 */
export async function signOut(): Promise<void> {
  let endSessionUrl: string | null = null;
  try {
    const { data } = await apiClient.POST('/api/auth/logout');
    endSessionUrl = data?.end_session_url ?? null;
  } catch (error) {
    // Even if logout fails server-side, drop local state and bounce.
    if (!(error instanceof ApiError) || !error.isAuthError) {
      console.warn('logout request failed', error);
    }
  }
  getQueryClient().setQueryData<CurrentUser | null>(userQueryKey, null);
  globalThis.location.assign(endSessionUrl ?? '/');
}

/**
 * Read the current user from the React Query cache. `user` is `null` when
 * signed out (or while the initial fetch is in flight, before `isLoading`
 * resolves).
 */
export function useUser(): {
  user: CurrentUser | null;
  isLoading: boolean;
} {
  const { data, isLoading } = useQuery({
    queryKey: userQueryKey,
    queryFn: () => fetchUser(),
    staleTime: 5 * 60_000,
  });
  return { user: data ?? null, isLoading };
}

/**
 * Prefetch the user query into the supplied query client. Used by the root
 * loader so SSR has user state available on first paint.
 */
export async function prefetchUser(
  queryClient: QueryClient,
  client: ApiClientType
): Promise<void> {
  await queryClient.prefetchQuery({
    queryKey: userQueryKey,
    queryFn: () => fetchUser(client),
  });
}
