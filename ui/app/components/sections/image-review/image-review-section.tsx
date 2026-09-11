import { BreadcrumbItem, Skeleton } from '@heroui/react';
import { InboxIcon } from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';

import { imageReviewQueueModelsQueryOptions } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { CompactBreadcrumbs } from '~/components/layout/breadcrumbs';
import { ImageReviewQueueCard } from './image-review-queue-card';

function CardSkeleton() {
  return (
    <div className="flex items-stretch justify-between gap-6 p-6 rounded-2xl">
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <Skeleton className="h-4 w-32 rounded" />
        <Skeleton className="h-6 w-80 max-w-full rounded-md" />
        <Skeleton className="h-3 w-64 rounded" />
      </div>
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
          No images awaiting review
        </h3>
        <p className="text-sm text-default-600 leading-relaxed">
          Nothing is waiting on an image review right now.
        </p>
      </div>
    </div>
  );
}

/**
 * Reviewer-facing queue of models awaiting Dockerfile/image review
 * (MISM-291, UI-Phase 6-A), gated on the `image_checker` capability at the
 * route loader (`~/routes/image-review`, via `requireCapability`).
 * Approve/reject actions (UI-Phase 6-B) live on each `ImageReviewQueueCard`.
 *
 * Unlike UI-Phase 4-A's Pending Reviews queue, this has no equivalent
 * backend-visibility gap: `approved` — the only registration status
 * `pending_image_check` can occur under — is the one status
 * `model_visible_to()` treats as fully public, so every candidate model is
 * visible to every caller regardless of role. See
 * `imageReviewQueueModelsQueryOptions`'s doc comment for the one real
 * limitation this queue does have (client-side filtering over a
 * `listModels`-capped page, not a server-side filter).
 */
export function ImageReviewSection() {
  const { data, isLoading, error, refetch } = useQuery(
    imageReviewQueueModelsQueryOptions()
  );
  const models = data?.results ?? [];

  let body: React.ReactNode;
  if (error) {
    body = (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load the image review queue"
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
          <ImageReviewQueueCard key={model.id} model={model} />
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
            <BreadcrumbItem>Image Review</BreadcrumbItem>
          </CompactBreadcrumbs>
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            Image Review
          </h1>
          <p className="mt-3 text-[16px] font-medium text-default-800/90">
            Models awaiting container image review.
          </p>
        </div>

        {body}
      </div>
    </main>
  );
}
