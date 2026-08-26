import cn from 'classnames';
import { Button, useDisclosure } from '@heroui/react';
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { CalendarIcon, UserIcon } from '@heroicons/react/16/solid';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';

import { reviewModelMetadata } from '~/api';
import type { ModelListItem } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { RejectReviewModal } from './reject-review-modal';

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.valueOf())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

interface ReviewQueueCardProps {
  model: ModelListItem;
}

/**
 * A reviewer's approve/reject decision on one pending model (MISM-291,
 * UI-Phase 4-B), via `POST /models/{id}/review`.
 *
 * Deliberately a separate component from `PendingReviewCard` (the
 * search-results embedded section), not a shared/extended one: that card's
 * "Review" button is the *owner's* self-service edit flow
 * (`/annotation-review?id=...`), a different action for a different
 * audience. Reconciling the two — whether the raw-YAML editor should stay
 * separate from this approve/reject action — is UI-Phase 4-C's decision,
 * not this step's; this card only adds the new action, and links to the
 * model detail page (not the editor) so a reviewer can inspect what
 * they're deciding on.
 */
export function ReviewQueueCard({ model }: ReviewQueueCardProps) {
  const queryClient = useQueryClient();
  const rejectModal = useDisclosure();
  const displayDate = model.date_published ?? model.created_at;

  const approveMutation = useMutation({
    mutationFn: () =>
      reviewModelMetadata(model.id, { approve: true, reason: '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modelKeys.pendingReview() });
    },
  });

  return (
    <div
      className={cn(
        'group relative p-6 rounded-2xl',
        'flex items-stretch justify-between gap-6',
        'transition-all duration-200',
        'bg-transparent hover:bg-warning/4',
        'hover:shadow-sm hover:shadow-warning/5 hover:-translate-y-px'
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
          <span
            className={cn(
              'inline-flex items-center px-2 py-0.5',
              'rounded-xs bg-warning',
              'text-white text-[10px] font-bold uppercase tracking-wide'
            )}
          >
            Model Pending Review
          </span>
        </div>

        <Link
          to={`/models/${encodeURIComponent(model.id)}`}
          className="text-xl font-bold font-headline text-primary hover:underline"
        >
          {model.name}
        </Link>

        {model.description && (
          <p className="text-sm text-default-800 line-clamp-2 mt-2 leading-relaxed">
            {model.description}
          </p>
        )}

        <div className="flex items-center gap-4 mt-3 min-h-8">
          <div
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2',
              'text-[11px] text-default-800 uppercase tracking-tight'
            )}
          >
            {model.owner && (
              <div className="flex items-center gap-1.5 font-medium text-primary">
                <UserIcon className="size-3.5" />
                <span>{model.owner}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="size-3.5" />
              <span>{formatDate(displayDate)}</span>
            </div>
          </div>
        </div>

        {approveMutation.isError && (
          <ApiErrorDisplay
            error={approveMutation.error}
            title="Failed to approve"
            className="mt-3"
          />
        )}
      </div>

      <RejectReviewModal
        model={model}
        isOpen={rejectModal.isOpen}
        onClose={rejectModal.onClose}
      />

      <div className="flex flex-col justify-between items-end gap-2">
        <Button
          size="sm"
          variant="flat"
          className={cn(
            'bg-transparent rounded-lg hover:opacity-100! active:opacity-90!',
            'text-danger hover:bg-danger hover:text-white'
          )}
          startContent={<XMarkIcon className="size-4" />}
          onPress={rejectModal.onOpen}
          isDisabled={approveMutation.isPending}
        >
          Reject
        </Button>
        <Button
          size="sm"
          color="success"
          className="min-w-24 rounded-lg text-white font-bold"
          startContent={<CheckIcon className="size-4" />}
          onPress={() => approveMutation.mutate()}
          isLoading={approveMutation.isPending}
        >
          Approve
        </Button>
      </div>
    </div>
  );
}
