import { useState } from 'react';
import {
  addToast,
  Button,
  closeToast,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
} from '@heroui/react';
import { XMarkIcon } from '@heroicons/react/24/solid';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';

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
  const navigate = useNavigate();
  const inputs = model.io_spec?.inputs ?? [];

  const buildInitialResourceIds = () =>
    inputs.map((_, i) => initialInputResourceIds?.[i] ?? '');

  const [resourceIds, setResourceIds] = useState<string[]>(
    buildInitialResourceIds
  );

  const mutation = useMutation<ExecuteRunResponse, Error, ExecuteRunRequest>({
    mutationFn: (body) => executeModelRun(model.id, body),
    onSuccess: (run) => {
      // Invalidate every run query so all views reflect the new run: the
      // "My Runs" page list (`runKeys.user(...)`, any status variant) and any
      // per-model list. Launching is rare, so the broad invalidation is cheap.
      void queryClient.invalidateQueries({ queryKey: runKeys.all });
      const viewRun = () => {
        // Dismiss the toast immediately as we navigate to the run.
        if (toastKey) closeToast(toastKey);
        navigate(`/runs?run=${encodeURIComponent(run.id)}`);
      };
      // Dark pill toast with an inline action row: [ View run | ✕ ]. We hide
      // HeroUI's default icon and floating close button and render the whole
      // right-side cluster ourselves in `endContent`, so there's no
      // color-tinted badge or absolute-positioned button to fight.
      const toastKey = addToast({
        title: 'Run started',
        description: `${model.name} is now running.`,
        // Slightly longer than the 6s default so there's time to hit "View".
        timeout: 8000,
        hideIcon: true,
        hideCloseButton: true,
        classNames: {
          base: 'rounded-xl bg-primary border-0 px-4 py-3 gap-x-6 shadow-lg items-center',
          wrapper: 'gap-y-0.5',
          title: 'text-sm font-bold text-white',
          description: 'text-xs text-white/80',
        },
        endContent: (
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={viewRun}
              className="text-sm font-semibold text-white underline underline-offset-2 hover:text-white/80 outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded"
            >
              View run
            </button>
            <span aria-hidden="true" className="h-5 w-px bg-white/25" />
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => toastKey && closeToast(toastKey)}
              className="text-white/80 hover:text-white outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded"
            >
              <XMarkIcon className="size-5" />
            </button>
          </div>
        ),
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
