import { BreadcrumbItem, Skeleton } from '@heroui/react';
import { InboxIcon } from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';

import { pendingReviewModelsQueryOptions } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { CompactBreadcrumbs } from '~/components/layout/breadcrumbs';
import { ReviewQueueCard } from './review-queue-card';

function CardSkeleton() {
  return (
    <div className="flex items-stretch justify-between gap-6 p-6 rounded-2xl">
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <Skeleton className="h-4 w-32 rounded" />
        <Skeleton className="h-6 w-80 max-w-full rounded-md" />
        <Skeleton className="h-3 w-64 rounded" />
      </div>
      <Skeleton className="h-8 w-32 rounded-lg" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center text-center gap-3 py-16">
      <InboxIcon
        className="size-10 text-default-400"
        aria-hidden="true"
        strokeWidth={1.25}
      />
      <div className="flex flex-col gap-1 max-w-sm">
        <h3 className="text-base font-semibold text-default-900">
          No pending reviews
        </h3>
        <p className="text-sm text-default-600 leading-relaxed">
          Nothing is waiting on review right now.
        </p>
      </div>
    </div>
  );
}

/**
 * Reviewer-facing queue of models pending metadata review (MISM-291,
 * UI-Phase 4-A), gated on the `upload_reviewer` capability at the route
 * loader (`~/routes/pending-reviews`, via `requireCapability`).
 *
 * KNOWN LIMITATION, not fixed here (see Docs/OpenFGA/MISM-291-UI-Plan.md,
 * UI-Phase 4-A's own note): `pendingReviewModelsQueryOptions()` filters
 * through the backend's `model_visible_to()`, a pure ownership check with
 * no `upload_reviewer` carve-out. Until that backend gap closes, this page
 * only shows the *caller's own* pending submissions, not the full review
 * backlog other uploaders created — the UI half of a reviewer queue, not
 * yet a working one end-to-end. Approve/reject wiring (UI-Phase 4-B) is
 * real and works for whatever this page's own visibility gap lets through.
 */
export function PendingReviewsSection() {
  const { data, isLoading, error, refetch } = useQuery(
    pendingReviewModelsQueryOptions()
  );
  const models = data?.results ?? [];

  let body: React.ReactNode;
  if (error) {
    body = (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load pending reviews"
        onRetry={refetch}
      />
    );
  } else if (isLoading) {
    body = (
      <div className="flex flex-col gap-2">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  } else if (models.length === 0) {
    body = <EmptyState />;
  } else {
    body = (
      <div className="flex flex-col">
        {models.map((model) => (
          <ReviewQueueCard key={model.id} model={model} />
        ))}
      </div>
    );
  }

  return (
    <main className="flex flex-col grow bg-default-50">
      <div className="max-w-4xl w-full mx-auto p-10 flex flex-col grow">
        <div className="mb-6">
          <CompactBreadcrumbs className="mb-3">
            <BreadcrumbItem href="/">Home</BreadcrumbItem>
            <BreadcrumbItem>Pending Reviews</BreadcrumbItem>
          </CompactBreadcrumbs>
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            Pending Reviews
          </h1>
          <p className="mt-3 text-[16px] font-medium text-default-800/90">
            Models awaiting metadata review.
          </p>
        </div>

        {body}
      </div>
    </main>
  );
}
