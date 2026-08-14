import type { QueryClient } from '@tanstack/react-query';
import { redirect } from 'react-router';

import { resolveUser, userQueryKey, type CurrentUser } from '~/api/auth/user';
import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';

/**
 * Reusable server-side auth guard for login-gated route loaders.
 *
 * Protection happens at the boundary, before the route renders: the user is
 * resolved from their session server-side and, if absent, the request is
 * redirected into the OIDC login flow. A gated view is therefore never shipped
 * to an anonymous visitor — no partially-rendered "please sign in" screen, no
 * leaked page chrome, no client-side flash.
 *
 * Usage in a gated route's `loader`:
 *
 *   export async function loader({ request }: Route.LoaderArgs) {
 *     const { user, client, queryClient } = await requireUser(request, {
 *       returnToKey: 'runs',
 *     });
 *     await queryClient.prefetchQuery(somethingQueryOptions(client));
 *     return { dehydratedState: dehydrate(queryClient) };
 *   }
 *
 * On success it returns the authenticated `user`, a cookie-forwarding
 * `client` for further per-request fetches, and a `queryClient` already seeded
 * with the user (so the browser doesn't re-fetch `/api/auth/me`).
 *
 * `returnToKey` must be a key in the API's server-side return_to allowlist
 * (`ROUTE_PATHS` in `api/.../auth/return_to.py`, kept in sync with the UI route
 * table) so the user lands back on this route after authenticating. The
 * allowlist is what keeps `return_to` safe from open-redirect abuse; unknown
 * keys fall back to the default landing path server-side.
 */
export async function requireUser(
  request: Request,
  options: { returnToKey?: string } = {}
): Promise<{
  user: CurrentUser;
  client: ReturnType<typeof serverApiClient>;
  queryClient: QueryClient;
}> {
  const client = serverApiClient(request);
  // `resolveUser`, not `fetchUser`: the root loader is resolving the same user
  // for this request, and this shares that single round-trip.
  const user = await resolveUser(request, client);

  if (!user) {
    throw redirect(buildLoginUrl(request, options.returnToKey));
  }

  const queryClient = getQueryClient();
  // Seed the resolved user so the client-side `useUser()` query hydrates from
  // cache instead of issuing another `/api/auth/me` round-trip on first paint.
  queryClient.setQueryData<CurrentUser | null>(userQueryKey, user);

  return { user, client, queryClient };
}

/**
 * Build the login URL, carrying a `return_to` route key + the current query so
 * the post-login callback returns the user to the route they were gated out
 * of. Mirrors the params `loginHref()` sends from the browser.
 */
function buildLoginUrl(request: Request, returnToKey?: string): string {
  const params = new URLSearchParams();
  if (returnToKey) {
    params.set('return_to_key', returnToKey);
    const query = new URL(request.url).search.replace(/^\?/, '');
    if (query) params.set('return_to_query', query);
  }
  const qs = params.toString();
  return `/api/auth/login${qs ? `?${qs}` : ''}`;
}
