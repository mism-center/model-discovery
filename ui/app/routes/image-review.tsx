import { HydrationBoundary, dehydrate } from '@tanstack/react-query';

import { requireCapability } from '~/api/auth/require-capability';
import { imageReviewQueueModelsQueryOptions } from '~/api/query/models';
import { ImageReviewSection } from '~/components/sections/image-review/image-review-section';
import type { Route } from './+types/image-review';

export function meta() {
  return [
    { title: 'Image Review | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Models awaiting container image review',
    },
  ];
}

/**
 * Capability-gated route (MISM-291, UI-Phase 6-A): only a caller holding
 * the platform-wide `image_checker` role reaches this page — see
 * `requireCapability`. Mirrors `pending-reviews.tsx`'s loader shape
 * exactly (UI-Phase 4-A), just gated on a different role.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const { client, queryClient } = await requireCapability(
    request,
    'image_checker',
    { returnToKey: 'image-review' }
  );

  // Prefetch for first paint. Swallow prefetch errors (mirroring
  // pending-reviews.tsx/runs.tsx/search.tsx) so a transient backend hiccup
  // renders the in-page error state rather than 500'ing the route.
  await queryClient.prefetchQuery(imageReviewQueueModelsQueryOptions(client));

  return { dehydratedState: dehydrate(queryClient) };
}

export default function ImageReview({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <ImageReviewSection />
    </HydrationBoundary>
  );
}
