import { useEffect, useState } from 'react';
import cn from 'classnames';
import {
  addToast,
  Button,
  closeToast,
  Divider,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Select,
  SelectItem,
} from '@heroui/react';
import { XMarkIcon } from '@heroicons/react/24/solid';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';

import {
  executeModelRun,
  type EntryPointDTO,
  type ExecuteRunRequest,
  type ExecuteRunResponse,
} from '~/api';
import type { RunnableModel } from '~/api/endpoints/runs';
import { runKeys } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';

interface RunModelModalProps {
  model: RunnableModel;
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
  /**
   * Command of the entry point the prior run used (rerun only). Matched by
   * command against the model's current entry points to preselect the same
   * one; if it no longer exists we fall back to the first entry point.
   */
  initialEntrypointCommand?: string | null;
  /**
   * Argument values the prior run used (rerun only), keyed by argument name.
   * Applied over declared defaults when the preselected entry point matches
   * the one the run used.
   */
  initialParameters?: Record<string, unknown>;
}

/** Stable label for an entry point in the selector. */
function entryPointLabel(entryPoint: EntryPointDTO, index: number): string {
  return entryPoint.command?.trim() || `Entry point ${index + 1}`;
}

/** Render an argument's declared default as an editable string value. */
function defaultArgValue(value: unknown): string {
  if (value == null) return '';
  return typeof value === 'string' ? value : String(value);
}

export function RunModelModal({
  model,
  isOpen,
  onClose,
  mode = 'batch',
  initialInputResourceIds,
  initialEntrypointCommand,
  initialParameters,
}: RunModelModalProps) {
  const queryClient = useQueryClient();
  const inputs = model.io_spec?.inputs ?? [];
  const entryPoints: EntryPointDTO[] = model.entry_points ?? [];

  const [resourceIds, setResourceIds] = useState<string[]>(() =>
    inputs.map((_, i) => initialInputResourceIds?.[i] ?? '')
  );
  // Index into `entryPoints` of the chosen entry point. Defaults to the first.
  const [entrypointIndex, setEntrypointIndex] = useState(0);
  // Argument override values for the selected entry point, keyed by argument
  // name (which is what the run API expects). We ignore `user_can_override`
  // for now and let users edit any argument the entry point declares.
  const [argValues, setArgValues] = useState<Record<string, string>>({});

  const selectedEntryPoint =
    entryPoints[entrypointIndex] ?? entryPoints[0] ?? undefined;
  const selectedArgs = selectedEntryPoint?.arguments ?? [];

  // On rerun, index of the entry point the prior run used (matched by command),
  // or -1 if none was given / it no longer exists.
  const rerunIndex = initialEntrypointCommand
    ? entryPoints.findIndex((ep) => ep.command === initialEntrypointCommand)
    : -1;

  // Argument values to seed for a given entry point: each argument's declared
  // default, except for the entry point a rerun is replaying, where the prior
  // run's values win.
  const seedArgValues = (index: number): Record<string, string> => {
    const args = entryPoints[index]?.arguments ?? [];
    const replaying = index === rerunIndex;
    return Object.fromEntries(
      args.map((arg) => {
        const rerunValue = replaying
          ? initialParameters?.[arg.name]
          : undefined;
        const value = rerunValue === undefined ? arg.default : rerunValue;
        return [arg.name, defaultArgValue(value)];
      })
    );
  };

  // Seed selection + argument values on mount.
  useEffect(() => {
    if (entryPoints.length === 0) return;
    const index = Math.max(rerunIndex, 0);
    setEntrypointIndex(index);
    setArgValues(seedArgValues(index));
  }, []);

  const mutation = useMutation<ExecuteRunResponse, Error, ExecuteRunRequest>({
    mutationFn: (body) => executeModelRun(model.id, body),
    onSuccess: (run) => {
      // Invalidate every run query so all views reflect the new run: the
      // "My Runs" page list (`runKeys.user(...)`, any status variant) and any
      // per-model list. Launching is rare, so the broad invalidation is cheap.
      void queryClient.invalidateQueries({ queryKey: runKeys.all });
      const runHref = `/runs?run=${encodeURIComponent(run.id)}`;
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
            <Link
              to={runHref}
              onClick={(event) => {
                // Only close the toast for a genuine left click. E.g., want to
                // avoid a ctrl-click opening in a new tab from closing the toast
                // in this tab. `Link` calls this before deciding whether to
                // navigate, so it runs on modified clicks too and must opt out.
                if (
                  event.metaKey ||
                  event.ctrlKey ||
                  event.shiftKey ||
                  event.altKey
                ) {
                  return;
                }
                if (toastKey) closeToast(toastKey);
              }}
              className="text-sm font-semibold text-white underline underline-offset-2 hover:text-white/80 outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded"
            >
              View run
            </Link>
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
      onClose();
    },
  });

  const handleClose = () => {
    if (mutation.isPending) return;
    onClose();
  };

  // Switching entry points re-seeds its argument values (defaults, or the prior
  // run's values if this is the entry point a rerun is replaying).
  const handleSelectEntrypoint = (index: number) => {
    setEntrypointIndex(index);
    setArgValues(seedArgValues(index));
  };

  const handleSubmit = () => {
    const trimmedIds = resourceIds.map((id) => id.trim());
    // Key overrides by argument name (what the run API consumes) and drop any
    // the user left blank so declared defaults apply server-side.
    const argumentEntries = selectedArgs
      .map((arg) => [arg.name, argValues[arg.name]?.trim() ?? ''] as const)
      .filter(([, value]) => value !== '');
    const argumentsPayload = Object.fromEntries(argumentEntries);

    mutation.mutate({
      input_resource_ids: trimmedIds,
      // Only send an index when the model actually declares entry points.
      entrypoint_index: entryPoints.length > 0 ? entrypointIndex : null,
      arguments: argumentsPayload,
      notes: '',
      mode,
    });
  };

  const requiredMissing = inputs.some(
    (slot, i) => slot.required && !resourceIds[i]?.trim()
  );

  // Pre-check for the backend's validate_image_approved_if_shipped gate
  // (MISM-291): a model that ships a container can't run until its image is
  // approved, distinct from — and reachable even after — the can_execute
  // pre-check RunControls already applies (UI-Phase 3-A gates *who* can
  // launch; this gates *whether the model itself is ready to*). Undefined
  // (search-originated launches, see RunnableModel's comment) is treated as
  // not blocked — best-effort, since the server remains the authoritative
  // check either way.
  const imageRejected = model.image_review_status === 'image_rejected';
  const imagePending = model.image_review_status === 'pending_image_check';
  const imageBlocked = imageRejected || imagePending;

  // Pre-check for the backend's validate_registration_approved gate (MISM-291):
  // only approved models are executable. Non-approved models are only visible
  // to their owner (model_visible_to enforces it), so this block is reachable
  // only by an owner whose metadata hasn't been approved yet. Undefined
  // (search-originated launches) is treated as not blocked — the search gate
  // already enforces approved-only, so those launches are always unblocked.
  const registrationBlocked =
    model.registration_status !== undefined &&
    model.registration_status !== 'approved';
  const registrationRejected = model.registration_status === 'rejected';
  const registrationPending = model.registration_status === 'pending_review';
  let registrationBlockMessage = '';
  if (registrationRejected) {
    registrationBlockMessage =
      "This model's metadata was rejected during review. The owner must resubmit it before this model can run.";
  } else if (registrationPending) {
    registrationBlockMessage =
      "This model's metadata is pending review. It can't run until it's approved.";
  } else if (registrationBlocked) {
    registrationBlockMessage =
      "This model hasn't completed metadata review and can't run yet.";
  }

  // Entry-point section: the selector and any argument inputs for the chosen
  // entry point. Built as a variable to keep the render free of nested
  // ternaries.
  let entryPointSection: React.ReactNode = null;
  if (entryPoints.length > 0) {
    entryPointSection = (
      <>
        <Divider className="my-1" />
        <div className="flex flex-col gap-4">
          <Select
            label="Entry point"
            description={selectedEntryPoint?.purpose || undefined}
            classNames={{ description: 'mt-1.5 text-default-700' }}
            selectedKeys={[String(entrypointIndex)]}
            disallowEmptySelection
            isDisabled={mutation.isPending || entryPoints.length === 1}
            onSelectionChange={(keys) => {
              const [key] = [...keys];
              if (key !== undefined) handleSelectEntrypoint(Number(key));
            }}
          >
            {entryPoints.map((entryPoint, i) => (
              <SelectItem
                key={String(i)}
                textValue={entryPointLabel(entryPoint, i)}
              >
                <span className="font-mono text-sm">
                  {entryPointLabel(entryPoint, i)}
                </span>
              </SelectItem>
            ))}
          </Select>

          {selectedArgs.length > 0 && (
            <div className="flex flex-col gap-3">
              <span className="text-xs font-medium text-default-800">
                Arguments
              </span>
              {selectedArgs.map((arg, i) => (
                <Input
                  key={`${arg.name}-${i}`}
                  label={arg.name}
                  description={arg.description || undefined}
                  classNames={{ description: 'mt-1.5 text-default-700' }}
                  placeholder="Value"
                  value={argValues[arg.name] ?? ''}
                  onValueChange={(value) =>
                    setArgValues((prev) => ({
                      ...prev,
                      [arg.name]: value,
                    }))
                  }
                  isDisabled={mutation.isPending}
                />
              ))}
            </div>
          )}
        </div>
      </>
    );
  }

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

          {imageBlocked && (
            <p
              className={cn(
                'rounded-md p-3 text-sm',
                imageRejected
                  ? 'bg-danger-50 text-danger-700'
                  : 'bg-warning-50 text-warning-700'
              )}
            >
              {imageRejected
                ? "This model's container image was rejected during review. The owner must resubmit it before this model can run."
                : "This model's container image is still pending review. It can't run until a reviewer approves the image."}
            </p>
          )}

          {registrationBlocked && (
            <p
              className={cn(
                'rounded-md p-3 text-sm',
                registrationRejected
                  ? 'bg-danger-50 text-danger-700'
                  : 'bg-warning-50 text-warning-700'
              )}
            >
              {registrationBlockMessage}
            </p>
          )}

          {inputs.length === 0 ? (
            <p className="text-sm text-default-700">
              This model doesn&apos;t accept a custom input dataset.
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {inputs.map((slot, i) => (
                <Input
                  key={`${slot.name}-${i}`}
                  label={slot.name}
                  description={slot.description || undefined}
                  classNames={{ description: 'mt-1.5 text-default-400' }}
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

          {entryPointSection}
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
            isDisabled={requiredMissing || imageBlocked || registrationBlocked}
          >
            Launch run
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
