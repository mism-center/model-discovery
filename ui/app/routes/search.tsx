import { HydrationBoundary, dehydrate } from '@tanstack/react-query';

import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';
import SearchSection from '~/components/sections/search/search';
import { searchQueryOptions } from '~/search/query/search-query';
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
 * Intentionally swallow prefetch errors here — if the backend is down or
 * returns 4xx we still want the route to render; the client-side useQuery
 * will retry and surface the error in the UI instead of 500'ing the page.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const state = searchStateFromParams(url.searchParams);

  const queryClient = getQueryClient();
  await queryClient.prefetchQuery(
    searchQueryOptions(state, serverApiClient(request))
  );

  return { dehydratedState: dehydrate(queryClient) };
}

export default function Search({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <SearchSection />
    </HydrationBoundary>
  );
}
