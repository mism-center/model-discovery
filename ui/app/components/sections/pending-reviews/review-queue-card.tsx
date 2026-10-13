import cn from 'classnames';
import { Button, useDisclosure } from '@heroui/react';
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { reviewModelMetadata } from '~/api';
import type { ModelListItem } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { useCapabilities } from '~/api/auth/capabilities';
import { useUser } from '~/api/auth/user';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { ReviewCard } from '~/components/common/review-card';
import { RejectReviewModal } from './reject-review-modal';

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
  const { capabilities } = useCapabilities();
  const { user } = useUser();
  const isOwner = !!user && model.owner === user.sub;

  const approveMutation = useMutation({
    mutationFn: () =>
      reviewModelMetadata(model.id, { approve: true, reason: '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modelKeys.pendingReview() });
    },
  });

  return (
    <ReviewCard
      badge="Annotation Pending Review"
      model={model}
      titleAs="link"
      subtitle={
        model.description && (
          <p className="text-sm text-default-800 line-clamp-2 mt-2 leading-relaxed">
            {model.description}
          </p>
        )
      }
      error={
        approveMutation.isError && (
          <ApiErrorDisplay
            error={approveMutation.error}
            title="Failed to approve"
            className="mt-3"
          />
        )
      }
      actions={
        <>
          <RejectReviewModal
            model={model}
            isOpen={rejectModal.isOpen}
            onClose={rejectModal.onClose}
          />
          <Button
            size="sm"
            variant="flat"
            className={cn(
              'bg-transparent rounded-lg hover:opacity-100! active:opacity-90!',
              'text-danger hover:bg-danger hover:text-white'
            )}
            startContent={<XMarkIcon className="size-4" />}
            onPress={rejectModal.onOpen}
            isDisabled={
              (!capabilities.upload_reviewer && !isOwner) ||
              approveMutation.isPending
            }
          >
            Reject
          </Button>
          <Button
            size="sm"
            color="primary"
            className="min-w-24 rounded-lg text-white font-bold"
            startContent={<CheckIcon className="size-4" />}
            onPress={() => approveMutation.mutate()}
            isLoading={approveMutation.isPending}
            isDisabled={
              (!capabilities.upload_reviewer && !isOwner) ||
              approveMutation.isPending
            }
          >
            Approve
          </Button>
        </>
      }
    />
  );
}
