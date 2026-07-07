import { useState } from 'react';
import {
  Button,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
} from '@heroui/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  executeModelRun,
  type ExecuteRunRequest,
  type ExecuteRunResponse,
  type SearchResultItem,
} from '~/api';
import { runKeys } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';

interface RunModelModalProps {
  model: SearchResultItem;
  isOpen: boolean;
  onClose: () => void;
  /**
   * v1 only supports batch. The prop is here so a future interactive
   * entrypoint can pass a different value without re-plumbing the form.
   */
  mode?: ExecuteRunRequest['mode'];
  /**
   * Pre-fill values for the launch form, used when rerunning a prior run.
   * Matched positionally against the model's declared inputs; missing
   * entries fall back to empty strings.
   */
  initialInputResourceIds?: string[];
}

export function RunModelModal({
  model,
  isOpen,
  onClose,
  mode = 'batch',
  initialInputResourceIds,
}: RunModelModalProps) {
  const queryClient = useQueryClient();
  const inputs = model.io_spec?.inputs ?? [];

  const buildInitialResourceIds = () =>
    inputs.map((_, i) => initialInputResourceIds?.[i] ?? '');

  const [resourceIds, setResourceIds] = useState<string[]>(
    buildInitialResourceIds
  );

  const mutation = useMutation<ExecuteRunResponse, Error, ExecuteRunRequest>({
    mutationFn: (body) => executeModelRun(model.id, body),
    onSuccess: () => {
      // Invalidate so the card immediately reflects the new active run. This
      // refetches the model's owned runs (a single request, only on launch),
      // replacing the search-embedded seed value.
      void queryClient.invalidateQueries({
        queryKey: runKeys.ownedByModel(model.id),
      });
      mutation.reset();
      setResourceIds(buildInitialResourceIds());
      onClose();
    },
  });

  const handleClose = () => {
    if (mutation.isPending) return;
    mutation.reset();
    setResourceIds(buildInitialResourceIds());
    onClose();
  };

  const handleSubmit = () => {
    const trimmedIds = resourceIds.map((id) => id.trim());
    mutation.mutate({
      input_resource_ids: trimmedIds,
      parameters: {},
      notes: '',
      mode,
    });
  };

  const requiredMissing = inputs.some(
    (slot, i) => slot.required && !resourceIds[i]?.trim()
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      isDismissable={!mutation.isPending}
      hideCloseButton={mutation.isPending}
      size="lg"
    >
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          <span className="text-lg font-bold text-primary">Run model</span>
          <span className="text-sm font-normal text-default-700">
            {model.name}
          </span>
        </ModalHeader>
        <ModalBody className="pt-0">
          {mutation.isError && (
            <ApiErrorDisplay
              error={mutation.error}
              title="Failed to launch run"
            />
          )}

          {inputs.length === 0 ? (
            <p className="text-sm text-default-700">
              This model declares no inputs. Submit to launch immediately.
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {inputs.map((slot, i) => (
                <Input
                  key={`${slot.name}-${i}`}
                  label={slot.name}
                  description={slot.description || undefined}
                  isRequired={slot.required}
                  placeholder="Resource ID"
                  value={resourceIds[i] ?? ''}
                  onValueChange={(value) =>
                    setResourceIds((prev) => {
                      const next = [...prev];
                      next[i] = value;
                      return next;
                    })
                  }
                  isDisabled={mutation.isPending}
                />
              ))}
            </div>
          )}
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
            onPress={handleSubmit}
            isLoading={mutation.isPending}
            isDisabled={requiredMissing}
          >
            Launch run
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
