import {
  Button,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
} from '@heroui/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { cancelRun, type RunDetailItem, type RunDetailResponse } from '~/api';
import { runKeys } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';

interface TerminateRunModalProps {
  run: RunDetailItem;
  isOpen: boolean;
  onClose: () => void;
}

export function TerminateRunModal({
  run,
  isOpen,
  onClose,
}: TerminateRunModalProps) {
  const queryClient = useQueryClient();

  const mutation = useMutation<RunDetailResponse, Error, void>({
    mutationFn: () => cancelRun(run.id),
    onSuccess: (response) => {
      queryClient.setQueryData<RunDetailResponse>(
        runKeys.detail(run.id),
        response
      );
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
          <span className="text-lg font-bold text-primary">Terminate run</span>
          <span className="text-xs text-default-600 font-normal">{run.id}</span>
        </ModalHeader>
        <ModalBody className="pt-0">
          {mutation.isError && (
            <ApiErrorDisplay
              error={mutation.error}
              title="Failed to terminate run"
            />
          )}
          <p className="text-sm text-default-700">
            This will stop the run immediately. Any in-progress work will be
            discarded and the run will be marked as cancelled.
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
            color="primary"
            onPress={() => mutation.mutate()}
            isLoading={mutation.isPending}
          >
            Confirm
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
