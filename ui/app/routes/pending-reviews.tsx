import { HydrationBoundary, dehydrate } from '@tanstack/react-query';

import { requireUser } from '~/api/auth/require-user';
import { pendingReviewModelsQueryOptions } from '~/api/query/models';
import { PendingReviewsSection } from '~/components/sections/pending-reviews/pending-reviews-section';
import type { Route } from './+types/pending-reviews';

export function meta() {
  return [
    { title: 'Pending Reviews | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Models awaiting metadata review',
    },
  ];
}

/**
 * Auth-gated route (MISM-291): any signed-in user reaches this page to see
 * and act on their own models awaiting metadata approval — see `requireUser`.
 * Mirrors `runs.tsx`'s loader shape exactly.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const { client, queryClient } = await requireUser(request, {
    returnToKey: 'pending-reviews',
  });

  // Prefetch for first paint. Swallow prefetch errors (mirroring runs.tsx/
  // search.tsx) so a transient backend hiccup renders the in-page error
  // state rather than 500'ing the route.
  await queryClient.prefetchQuery(pendingReviewModelsQueryOptions(client));

  return { dehydratedState: dehydrate(queryClient) };
}

export default function PendingReviews({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <PendingReviewsSection />
    </HydrationBoundary>
  );
}
