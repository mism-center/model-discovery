import { Button, useDisclosure } from '@heroui/react';
import { ArrowUpTrayIcon } from '@heroicons/react/24/solid';

import { useUser } from '~/api/auth/user';
import type { ModelDetailResponse } from '~/api/endpoints/models';
import { SubmitContainerImageModal } from './submit-container-image-modal';

/**
 * Owner-facing entry point for submitting (or resubmitting) a built
 * container image for `image_checker` review (MISM-291, UI-Phase 5-A).
 *
 * Visible only when all three hold:
 *   - the viewer owns the model — the backend gates the endpoint on
 *     ownership alone, with no OpenFGA role carve-out (see
 *     `submit_container_image`'s docstring in `mismapi/api/v1/models.py`);
 *   - `registration_status === 'approved'` — the backend's
 *     `validate_registration_approved` precondition; and
 *   - `image_review_status !== 'pending_image_check'` — submitting while a
 *     decision is already pending is not a legal transition
 *     (`_VALID_IMAGE_REVIEW_TRANSITIONS` in `mism_registry.validation` has
 *     no self-loop for `PENDING_IMAGE_CHECK`), so the button never offers
 *     an action the server would just reject.
 *
 * This is why the action lives in `ExecutionSection` outside both the
 * `hasContent` early-return and the `EXECUTION_BLOCKS` loop: it must be
 * reachable for a freshly-approved model that has no container yet at
 * all — exactly the case that would otherwise short-circuit to
 * `SectionAbsence` before ever reaching the Containers block.
 */
export function SubmitContainerImageAction({
  model,
}: {
  model: ModelDetailResponse;
}) {
  const { user } = useUser();
  const disclosure = useDisclosure();

  const isOwner = Boolean(user) && user?.sub === model.owner;
  const isApproved = model.registration_status === 'approved';
  const isPendingImageCheck =
    model.image_review_status === 'pending_image_check';

  if (!isOwner || !isApproved || isPendingImageCheck) return null;

  const hasExistingContainer = Boolean(model.containers?.length);

  return (
    <div className="mt-6">
      <Button
        size="sm"
        color="primary"
        variant="flat"
        startContent={<ArrowUpTrayIcon className="size-4" />}
        onPress={disclosure.onOpen}
      >
        {hasExistingContainer
          ? 'Resubmit container image'
          : 'Submit container image'}
      </Button>
      {/* Mount only while open so each open starts from fresh form state. */}
      {disclosure.isOpen && (
        <SubmitContainerImageModal
          model={model}
          isOpen
          onClose={disclosure.onClose}
        />
      )}
    </div>
  );
}
