import { HydrationBoundary, dehydrate } from '@tanstack/react-query';

import { requireCapability } from '~/api/auth/require-capability';
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
 * Capability-gated route (MISM-291, UI-Phase 4-A): only a caller holding
 * the platform-wide `upload_reviewer` role reaches this page — see
 * `requireCapability`. Mirrors `runs.tsx`'s loader shape exactly, just
 * with a role check layered onto the auth check.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const { client, queryClient } = await requireCapability(
    request,
    'upload_reviewer',
    { returnToKey: 'pending-reviews' }
  );

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
