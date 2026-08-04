import { useQuery, type QueryClient } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';
import { ApiError } from '~/api/client/errors';

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
  '/runs': 'runs',
  '/upload': 'upload',
  '/annotation-review': 'annotation-review',
};

/**
 * Parameterized routes, matched by prefix, that can be returned to after login.
 *
 * The client sends a route *key* plus the id as a separate value — never a path.
 * The server resolves the key against its own allowlist and validates the id as a
 * UUID before substituting it (`mismapi/auth/return_to.py`), so a hostile id
 * can't graft segments or an origin onto the redirect. Keep in sync with
 * `PARAMETERIZED_ROUTE_PATHS` there.
 */
const RETURN_TO_ID_ROUTES: Array<{ prefix: string; key: string }> = [
  { prefix: '/models/', key: 'model' },
];

/**
 * Trigger an OIDC login. Top-level navigation so the browser follows the
 * 302 chain to the IdP and back through `/api/auth/callback` cleanly. Sends
 * the current route key + query so the callback can return the user here.
 */
export function signIn(): void {
  const pathname = globalThis.location.pathname;
  let key = RETURN_TO_KEYS[pathname];
  let id: string | undefined;

  if (!key) {
    const match = RETURN_TO_ID_ROUTES.find((route) =>
      pathname.startsWith(route.prefix)
    );
    const candidate = match ? pathname.slice(match.prefix.length) : undefined;
    // Only a single trailing segment is a candidate id; anything with a further
    // `/` is a different route and is left unmapped (server falls back too).
    if (match && candidate && !candidate.includes('/')) {
      key = match.key;
      id = candidate;
    }
  }

  const params = new URLSearchParams();
  if (key) {
    params.set('return_to_key', key);
    if (id) params.set('return_to_id', id);
    const query = globalThis.location.search.replace(/^\?/, '');
    if (query) params.set('return_to_query', query);
  }
  const qs = params.toString();
  globalThis.location.assign(`/api/auth/login${qs ? `?${qs}` : ''}`);
}

/**
 * End the session and, if the IdP supports RP-initiated logout, navigate
 * top-level to its `end_session_endpoint` so the IdP can clear its own session.
 * Otherwise land on `/`.
 *
 * Deliberately does *not* write `null` into the user query first. This always
 * ends in a full-page navigation, so the cache is about to be discarded with the
 * document — but `location.assign` doesn't block, so flipping the cache first
 * gave React time to commit a signed-out render and repaint it for the whole
 * duration of the navigation. That was invisible while logging out only removed
 * a button; once it also unmounted the run-history section, dropped a nav-rail
 * entry and hid two navbar links, it became a visible 0.5–1s rearrangement
 * before the redirect.
 */
export async function signOut(): Promise<void> {
  let endSessionUrl: string | null = null;
  try {
    const { data } = await apiClient.POST('/api/auth/logout');
    endSessionUrl = data?.end_session_url ?? null;
  } catch (error) {
    // Even if logout fails server-side, bounce anyway — the server has already
    // deleted the session cookie in every case it reaches.
    if (!(error instanceof ApiError) || !error.isAuthError) {
      console.warn('logout request failed', error);
    }
  }
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
 * In-flight user resolution, keyed by the HTTP request it belongs to.
 *
 * Every matched loader runs for a single navigation, and each builds its own
 * QueryClient — `getQueryClient()` is deliberately fresh per call on the server
 * so caches never leak between users. The cost was that root's loader and the
 * route's loader each issued their own `/api/auth/me`, making two identical
 * authenticated round-trips per navigation.
 *
 * A `Request` belongs to exactly one HTTP request, so a cached entry here can
 * never be observed by another user — the dedupe is safe by construction rather
 * than by discipline. And if React Router ever stopped handing every matched
 * loader the same `Request` instance, this would quietly stop deduping instead of
 * returning the wrong user.
 *
 * A `WeakMap` so entries are collectable as soon as the request is done; there is
 * no eviction to get wrong.
 */
const userByRequest = new WeakMap<Request, Promise<CurrentUser | null>>();

/**
 * Resolve the current user once per request, sharing the result across every
 * loader that asks. Server-side only — pass the loader's `request`.
 */
export function resolveUser(
  request: Request,
  client: ApiClientType
): Promise<CurrentUser | null> {
  const inFlight = userByRequest.get(request);
  if (inFlight) return inFlight;

  const pending = fetchUser(client);
  userByRequest.set(request, pending);
  return pending;
}

/**
 * Prefetch the user query into the supplied query client, so SSR has user state
 * on first paint.
 *
 * Only the root loader needs this. Root's `HydrationBoundary` wraps the whole
 * route tree and hydrates synchronously during render, so `useUser()` is already
 * populated before any route component renders — a route prefetching the user
 * again only adds a second request and a redundant hydration of the same key.
 * A loader that needs the *value* server-side should call `resolveUser`.
 */
export async function prefetchUser(
  queryClient: QueryClient,
  client: ApiClientType,
  request: Request
): Promise<void> {
  await queryClient.prefetchQuery({
    queryKey: userQueryKey,
    queryFn: () => resolveUser(request, client),
  });
}
