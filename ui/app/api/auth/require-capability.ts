import type { QueryClient } from '@tanstack/react-query';
import { redirect } from 'react-router';

import {
  resolveCapabilities,
  capabilitiesQueryKey,
  type AuthCapabilities,
} from '~/api/auth/capabilities';
import { resolveUser, userQueryKey, type CurrentUser } from '~/api/auth/user';
import { buildLoginUrl } from '~/api/auth/require-user';
import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';

/**
 * Reusable server-side capability guard for role-gated route loaders.
 * Mirrors `requireUser`'s "protect at the boundary, before the route
 * renders" shape exactly, extended with a platform-role check:
 *
 *   - anonymous visitor → redirected into login (same as `requireUser` — a
 *     role can only ever belong to a signed-in principal, so this might
 *     actually fix the problem)
 *   - signed-in visitor lacking the given capability → redirected home,
 *     not back to login (which wouldn't fix anything for them)
 *
 * Neither case ships the gated page's content or data.
 *
 * Usage in a gated route's `loader`:
 *
 *   export async function loader({ request }: Route.LoaderArgs) {
 *     const { client, queryClient } = await requireCapability(
 *       request,
 *       'upload_reviewer',
 *       { returnToKey: 'pending-reviews' }
 *     );
 *     await queryClient.prefetchQuery(somethingQueryOptions(client));
 *     return { dehydratedState: dehydrate(queryClient) };
 *   }
 *
 * `returnToKey` behaves exactly as it does for `requireUser` — see that
 * file's docstring. A key not yet registered in the API's server-side
 * return_to allowlist just falls back to the default landing path (a minor,
 * non-breaking UX gap, not wired up here since it needs a backend change).
 */
export async function requireCapability(
  request: Request,
  capability: keyof AuthCapabilities,
  options: { returnToKey?: string } = {}
): Promise<{
  user: CurrentUser;
  capabilities: AuthCapabilities;
  client: ReturnType<typeof serverApiClient>;
  queryClient: QueryClient;
}> {
  const client = serverApiClient(request);
  const user = await resolveUser(request, client);

  if (!user) {
    throw redirect(buildLoginUrl(request, options.returnToKey));
  }

  const capabilities = await resolveCapabilities(request, client);
  if (!capabilities[capability]) {
    throw redirect('/');
  }

  const queryClient = getQueryClient();
  // Seed both so client-side useUser()/useCapabilities() hydrate from cache
  // instead of issuing another round-trip on first paint.
  queryClient.setQueryData<CurrentUser | null>(userQueryKey, user);
  queryClient.setQueryData<AuthCapabilities>(
    capabilitiesQueryKey,
    capabilities
  );

  return { user, capabilities, client, queryClient };
}
