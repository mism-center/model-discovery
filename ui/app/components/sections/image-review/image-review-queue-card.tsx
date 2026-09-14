import cn from 'classnames';
import { Button, useDisclosure } from '@heroui/react';
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { reviewModelContainerImage } from '~/api';
import type { ModelListItem } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { ReviewCard } from '~/components/common/review-card';
import { RejectImageModal } from './reject-image-modal';

interface ImageReviewQueueCardProps {
  model: ModelListItem;
}

/**
 * A reviewer's approve/reject decision on one model's pending container
 * image (MISM-291, UI-Phase 6-B), via `POST /models/{id}/image-review`.
 *
 * Mirrors `ReviewQueueCard` (UI-Phase 4-B) exactly, one level down the
 * workflow: Approve fires directly (no modal — a routine, low-friction
 * action); Reject opens `RejectImageModal`, since the backend requires a
 * non-blank reason for it. Links to the model detail page, not an editor —
 * there is no owner-facing image editor to link to instead.
 */
export function ImageReviewQueueCard({ model }: ImageReviewQueueCardProps) {
  const queryClient = useQueryClient();
  const rejectModal = useDisclosure();
  const container = model.containers?.[0];

  const approveMutation = useMutation({
    mutationFn: () =>
      reviewModelContainerImage(model.id, { approve: true, reason: '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: modelKeys.imageReviewQueue(),
      });
    },
  });

  return (
    <ReviewCard
      badge="Image Pending Review"
      model={model}
      titleAs="link"
      subtitle={
        container ? (
          <p className="text-sm text-default-900 mt-2">
            <span className="font-semibold capitalize">{container.kind}</span>
            {container.image_name && (
              <span className="font-mono"> · {container.image_name}</span>
            )}
            {container.registry && (
              <span className="text-default-800"> · {container.registry}</span>
            )}
            {container.file && (
              <span className="text-default-800"> ({container.file})</span>
            )}
          </p>
        ) : undefined
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
          <RejectImageModal
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
            isDisabled={approveMutation.isPending}
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
          >
            Approve
          </Button>
        </>
      }
    />
  );
}
