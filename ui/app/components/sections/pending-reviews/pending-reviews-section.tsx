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
          No annotation review
        </h3>
        <p className="text-sm text-default-600 leading-relaxed">
          Nothing is waiting on review right now.
        </p>
      </div>
    </div>
  );
}

/**
 * Owner-facing list of models the signed-in user submitted that are still
 * awaiting their metadata approval (MISM-291). Gated on authentication only
 * (`~/routes/pending-reviews`, via `requireUser`).
 *
 * The backend's `model_visible_to()` filter returns only the caller's own
 * resources, so this page naturally shows only the user's own pending
 * submissions — which is the intended behavior: each uploader reviews and
 * approves their own models rather than a shared reviewer queue.
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
        title="Couldn't load annotation review"
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
            <BreadcrumbItem>Annotation Review</BreadcrumbItem>
          </CompactBreadcrumbs>
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            Annotation Review
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
