import { HydrationBoundary, dehydrate } from '@tanstack/react-query';

import { prefetchUser, userQueryKey, type CurrentUser } from '~/api/auth/user';
import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';
import { modelRunsQueryOptions } from '~/api/query/runs';
import SearchSection from '~/components/sections/search/search';
import { searchQueryOptions } from '~/api/query/search';
import { searchStateFromParams } from '~/search/state/url-codec';
import type { Route } from './+types/search';

export function meta() {
  return [
    { title: 'Search | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Search for multiscale models and datasets',
    },
  ];
}

/**
 * Prefetch the search response on the server so the first paint has data.
 *
 * Once the search response is in hand, prefetch run history for every
 * executable model on the page, but only when the request carries an
 * authenticated session.
 *
 * Intentionally swallow prefetch errors here — if the backend is down or
 * returns 4xx we still want the route to render; the client-side useQuery
 * will retry and surface the error in the UI instead of 500'ing the page.
 * Per-model run prefetches are best-effort for the same reason: a single
 * model failing shouldn't block the page.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const state = searchStateFromParams(url.searchParams);
  const client = serverApiClient(request);

  const queryClient = getQueryClient();
  await Promise.all([
    queryClient.prefetchQuery(searchQueryOptions(state, client)),
    prefetchUser(queryClient, client),
  ]);

  const user = queryClient.getQueryData<CurrentUser | null>(userQueryKey);
  if (user) {
    const searchData = queryClient.getQueryData(
      searchQueryOptions(state).queryKey
    );
    const executableModelIds = (searchData?.results ?? [])
      .filter((result) => Boolean(result.execution_type))
      .map((result) => result.id);

    await Promise.all(
      executableModelIds.map((modelId) =>
        queryClient.prefetchQuery(modelRunsQueryOptions(modelId, client))
      )
    );
  }

  return { dehydratedState: dehydrate(queryClient) };
}

export default function Search({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <SearchSection />
    </HydrationBoundary>
  );
}
