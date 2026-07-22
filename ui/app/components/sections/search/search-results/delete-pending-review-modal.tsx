import {
  Button,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
} from '@heroui/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import type { ModelListItem } from '~/api/endpoints/models';
import { deleteModel } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';

interface DeletePendingReviewModalProps {
  model: ModelListItem;
  isOpen: boolean;
  onClose: () => void;
}

export function DeletePendingReviewModal({
  model,
  isOpen,
  onClose,
}: DeletePendingReviewModalProps) {
  const queryClient = useQueryClient();

  const mutation = useMutation<void, Error, void>({
    mutationFn: () => deleteModel(model.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modelKeys.pendingReview() });
      mutation.reset();
      onClose();
    },
  });

  const handleClose = () => {
    if (mutation.isPending) return;
    mutation.reset();
    onClose();
  };

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
          <span className="text-lg font-bold text-danger">
            Delete annotation
          </span>
          <span className="text-xs text-default-600 font-normal">
            {model.name}
          </span>
        </ModalHeader>
        <ModalBody className="pt-0">
          {mutation.isError && (
            <ApiErrorDisplay
              error={mutation.error}
              title="Failed to delete annotation"
            />
          )}
          <p className="text-sm text-default-700">
            This will permanently remove the model record and all associated
            annotation files from the file system. This action cannot be undone.
          </p>
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
          >
            Delete
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
