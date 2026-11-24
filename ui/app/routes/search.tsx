import { HydrationBoundary, dehydrate } from '@tanstack/react-query';
import type { ShouldRevalidateFunctionArgs } from 'react-router';

import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';
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
 * The search response embeds each executable model's run history for the
 * authenticated caller (`owned_runs`).
 *
 * Intentionally swallow prefetch errors here — if the backend is down or
 * returns 4xx we still want the route to render; the client-side useQuery
 * will retry and surface the error in the UI instead of 500'ing the page.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const state = searchStateFromParams(url.searchParams);
  const client = serverApiClient(request);

  const queryClient = getQueryClient();
  // The user is not prefetched here: the root loader already does it, and its
  // HydrationBoundary wraps this route, so `useUser()` is populated before
  // anything here renders.
  await queryClient.prefetchQuery(searchQueryOptions(state, client));

  return { dehydratedState: dehydrate(queryClient) };
}

/**
 * The loader exists for server-side first paint, seeding the dehydrated
 * React Query cache so the SSR HTML has data. Once hydrated, React Query owns
 * refetching: changing the search state produces a new query key and refetches
 * reactively. So skip the loader for same-route search-param navigations
 * (pagination, facets, sort, query). Still revalidate across pathname changes
 * and on explicit router revalidation.
 */
export function shouldRevalidate({
  currentUrl,
  nextUrl,
  defaultShouldRevalidate,
}: ShouldRevalidateFunctionArgs) {
  if (currentUrl.pathname === nextUrl.pathname) return false;
  return defaultShouldRevalidate;
}

export default function Search({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <SearchSection />
    </HydrationBoundary>
  );
}
