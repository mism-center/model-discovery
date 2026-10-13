import { useState } from 'react';
import {
  Button,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Textarea,
} from '@heroui/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { reviewModelMetadata } from '~/api';
import type { ModelListItem } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';

interface RejectReviewModalProps {
  model: ModelListItem;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Reject action for a pending model's metadata review (MISM-291,
 * UI-Phase 4-B), via `POST /models/{id}/review` with `approve: false`.
 *
 * Approve (in `ReviewQueueCard`) fires directly on click, no modal — a
 * routine, low-friction reviewer action. Reject gets a modal specifically
 * because the backend requires a non-blank reason for it (a
 * `model_validator` on `ReviewMetadataPackageRequest`); `reasonMissing`
 * mirrors that requirement client-side so a blank reason never reaches the
 * network round trip at all.
 */
export function RejectReviewModal({
  model,
  isOpen,
  onClose,
}: RejectReviewModalProps) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState('');

  const mutation = useMutation({
    mutationFn: () =>
      reviewModelMetadata(model.id, {
        approve: false,
        reason: reason.trim(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modelKeys.pendingReview() });
      mutation.reset();
      setReason('');
      onClose();
    },
  });

  const handleClose = () => {
    if (mutation.isPending) return;
    mutation.reset();
    setReason('');
    onClose();
  };

  const reasonMissing = reason.trim() === '';

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      isDismissable={!mutation.isPending}
      hideCloseButton={mutation.isPending}
      size="md"
    >
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          <span className="text-lg font-bold text-danger">Reject metadata</span>
          <span className="text-xs text-default-600 font-normal">
            {model.name}
          </span>
        </ModalHeader>
        <ModalBody className="pt-0">
          {mutation.isError && (
            <ApiErrorDisplay error={mutation.error} title="Failed to reject" />
          )}
          <Textarea
            label="Reason"
            description="Shown to the model's owner so they know what to fix before resubmitting."
            placeholder="e.g. Missing entry point documentation."
            value={reason}
            minRows={3}
            onValueChange={setReason}
            isRequired
            isDisabled={mutation.isPending}
            classNames={{ label: 'text-xs text-default-800 font-medium' }}
          />
        </ModalBody>
        <ModalFooter>
          <Button
            variant="light"
            onPress={handleClose}
            isDisabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            color="danger"
            onPress={() => mutation.mutate()}
            isLoading={mutation.isPending}
            isDisabled={reasonMissing}
          >
            Reject
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
