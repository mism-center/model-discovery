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

import { submitModelContainerImage } from '~/api';
import type { ModelDetailResponse } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';

interface SubmitContainerImageModalProps {
  model: ModelDetailResponse;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Form for `POST /models/{id}/image` (MISM-291, UI-Phase 5-A).
 *
 * Fields mirror `SubmitContainerImageRequest` exactly: only `kind` is
 * required server-side (it has no default, unlike `file`/`image_name`/
 * `registry`, which all default to `""`), so `kind` is the one field marked
 * required here. Pre-filled from the model's current (first) container, if
 * any, so a resubmit after rejection starts from what was already there
 * rather than a blank form.
 *
 * `kind` is a free-text `Input`, not a `Select`: the backend stores and
 * validates it as an unconstrained string (no enum — see `ContainerDTO`),
 * so offering a fixed list would imply a constraint that does not exist.
 */
export function SubmitContainerImageModal({
  model,
  isOpen,
  onClose,
}: SubmitContainerImageModalProps) {
  const queryClient = useQueryClient();
  const existing = model.containers?.[0];
  const [kind, setKind] = useState(existing?.kind ?? '');
  const [file, setFile] = useState(existing?.file ?? '');
  const [imageName, setImageName] = useState(existing?.image_name ?? '');
  const [registry, setRegistry] = useState(existing?.registry ?? '');

  const mutation = useMutation({
    mutationFn: () =>
      submitModelContainerImage(model.id, {
        kind: kind.trim(),
        file: file.trim(),
        image_name: imageName.trim(),
        registry: registry.trim(),
      }),
    onSuccess: () => {
      // The detail query is this action's only visible effect (a fresh
      // `image_review_status`/`containers`), so that alone needs
      // invalidating.
      queryClient.invalidateQueries({ queryKey: modelKeys.detail(model.id) });
      onClose();
    },
  });

  const handleClose = () => {
    if (mutation.isPending) return;
    mutation.reset();
    onClose();
  };

  const kindMissing = kind.trim() === '';
  const isResubmit = model.image_review_status === 'image_rejected';

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
          <span className="text-lg font-bold text-primary">
            {isResubmit ? 'Resubmit container image' : 'Submit container image'}
          </span>
          <span className="text-sm font-normal text-default-700">
            {model.name}
          </span>
        </ModalHeader>
        <ModalBody className="pt-0">
          {mutation.isError && (
            <ApiErrorDisplay
              error={mutation.error}
              title="Failed to submit container image"
            />
          )}
          {isResubmit && model.image_rejection_reason && (
            <p className="rounded-md bg-danger-50 p-3 text-sm text-danger-700">
              Rejected: {model.image_rejection_reason}
            </p>
          )}
          <div className="flex flex-col gap-4">
            <Input
              label="Kind"
              description="e.g. docker"
              classNames={{ description: 'mt-1.5 text-default-700' }}
              isRequired
              value={kind}
              onValueChange={setKind}
              isDisabled={mutation.isPending}
            />
            <Input
              label="File"
              description="Path to the Dockerfile or build definition, if applicable."
              classNames={{ description: 'mt-1.5 text-default-700' }}
              value={file}
              onValueChange={setFile}
              isDisabled={mutation.isPending}
            />
            <Input
              label="Image name"
              value={imageName}
              onValueChange={setImageName}
              isDisabled={mutation.isPending}
            />
            <Input
              label="Registry"
              value={registry}
              onValueChange={setRegistry}
              isDisabled={mutation.isPending}
            />
          </div>
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
            isDisabled={kindMissing}
          >
            Submit
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
