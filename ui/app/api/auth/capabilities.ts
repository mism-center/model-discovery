import { useQuery, type QueryClient } from '@tanstack/react-query';
import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';
import { ApiError } from '~/api/client/errors';

export type AuthCapabilities = components['schemas']['AuthCapabilities'];

export const capabilitiesQueryKey = ['auth', 'capabilities'] as const;

type ApiClientType = Client<paths>;

/**
 * No role grants — the same state an anonymous caller and a signed-in user
 * holding none of the four platform roles both read as. Also what
 * `fetchCapabilities` falls back to on 401, so a caller who is simply not
 * signed in never has to special-case "no data yet" vs. "definitely none".
 */
const NO_CAPABILITIES: AuthCapabilities = {
  uploader: false,
  upload_reviewer: false,
  image_checker: false,
  executor: false,
};

/**
 * Fetch the calling principal's platform-wide role grants. 401 from the API
 * means "not signed in", which is a normal state here exactly as it is for
 * `fetchUser` — return all-false rather than throwing. Other failures
 * propagate so the query lands in an error state and the UI can surface it.
 */
export async function fetchCapabilities(
  client: ApiClientType = apiClient
): Promise<AuthCapabilities> {
  try {
    const { data } = await client.GET('/api/auth/capabilities');
    return data ?? NO_CAPABILITIES;
  } catch (error) {
    if (error instanceof ApiError && error.isAuthError) return NO_CAPABILITIES;
    throw error;
  }
}

/**
 * Read the calling principal's capabilities from the React Query cache.
 * `capabilities` is all-false when signed out (or while the initial fetch
 * is in flight, before `isLoading` resolves) — never `null`/`undefined`, so
 * callers can index straight into `capabilities.upload_reviewer` etc.
 * without a presence check first.
 */
export function useCapabilities(): {
  capabilities: AuthCapabilities;
  isLoading: boolean;
} {
  const { data, isLoading } = useQuery({
    queryKey: capabilitiesQueryKey,
    queryFn: () => fetchCapabilities(),
    staleTime: 5 * 60_000,
  });
  return { capabilities: data ?? NO_CAPABILITIES, isLoading };
}

/**
 * In-flight capabilities resolution, keyed by the HTTP request it belongs
 * to. Mirrors `userByRequest` in `user.ts` — see that file's comment for why
 * a `WeakMap` keyed on `Request` is safe to dedupe on without an eviction
 * policy.
 */
const capabilitiesByRequest = new WeakMap<Request, Promise<AuthCapabilities>>();

/**
 * Resolve capabilities once per request, sharing the result across every
 * loader that asks. Server-side only — pass the loader's `request`.
 */
export function resolveCapabilities(
  request: Request,
  client: ApiClientType
): Promise<AuthCapabilities> {
  const inFlight = capabilitiesByRequest.get(request);
  if (inFlight) return inFlight;

  const pending = fetchCapabilities(client);
  capabilitiesByRequest.set(request, pending);
  return pending;
}

/**
 * Prefetch the capabilities query into the supplied query client, so SSR has
 * capability state on first paint. Not yet wired into `root.tsx` — that is
 * UI-Phase 2-B's job, once capabilities join the app-wide session context
 * alongside `useUser()`.
 */
export async function prefetchCapabilities(
  queryClient: QueryClient,
  client: ApiClientType,
  request: Request
): Promise<void> {
  await queryClient.prefetchQuery({
    queryKey: capabilitiesQueryKey,
    queryFn: () => resolveCapabilities(request, client),
  });
}
