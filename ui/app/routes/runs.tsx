import { HydrationBoundary, dehydrate } from '@tanstack/react-query';
import type { ShouldRevalidateFunctionArgs } from 'react-router';

import { requireUser } from '~/api/auth/require-user';
import { userRunsQueryOptions } from '~/api/query/runs';
import MyRunsSection from '~/components/sections/runs/my-runs';
import type { Route } from './+types/runs';

export function meta() {
  return [
    { title: 'My Runs | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Your model runs',
    },
  ];
}

/**
 * Auth-gated route. `requireUser` resolves the session server-side and
 * redirects anonymous visitors into the login flow before this route renders,
 * so the gated view is never shipped to someone without a session. Only once
 * the user is confirmed do we prefetch their runs for first paint.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const { client, queryClient } = await requireUser(request, {
    returnToKey: 'runs',
  });

  // Prefetch runs for first paint. Swallow prefetch errors (mirroring
  // search.tsx) so a transient backend hiccup renders the in-page error state
  // rather than 500'ing the route.
  await queryClient.prefetchQuery(userRunsQueryOptions(undefined, client));

  return { dehydratedState: dehydrate(queryClient) };
}

/**
 * Skip the loader for same-route navigations (e.g. status filter search
 * params); React Query owns refetching once hydrated. Revalidate across
 * pathname changes and explicit router revalidation.
 */
export function shouldRevalidate({
  currentUrl,
  nextUrl,
  defaultShouldRevalidate,
}: ShouldRevalidateFunctionArgs) {
  if (currentUrl.pathname === nextUrl.pathname) return false;
  return defaultShouldRevalidate;
}

export default function Runs({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <MyRunsSection />
    </HydrationBoundary>
  );
}
