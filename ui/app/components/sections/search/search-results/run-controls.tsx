import { Button, Tooltip, useDisclosure } from '@heroui/react';
import { PlayIcon } from '@heroicons/react/24/solid';

import type { RunnableModel } from '~/api/endpoints/runs';
import { useUser } from '~/api/auth/user';
import { useCapabilities } from '~/api/auth/capabilities';
import { RunModelModal } from './run-model-modal';

interface RunControlsProps {
  model: RunnableModel;
  /**
   * Visual scale of the launch button.
   *
   * `'card'` (the default) is a search result row: a compact icon-only button
   * that pairs with the bookmark button already in that column. It is the row's
   * only action — navigation belongs to the card itself, which is a link — so it
   * needs no label to distinguish it from anything.
   *
   * `'page'` is the detail page, where this is the primary verb beside a
   * `text-3xl` heading and stays labelled.
   */
  scale?: 'card' | 'page';
}

/**
 * Launch affordance for an executable model.
 *
 *   - executable + signed in + can_execute → launch button (opens the launch modal)
 *   - non-executable, signed out, or lacking can_execute → render nothing
 *
 * Running is an authenticated action — the server rejects anonymous launches —
 * so nothing renders until a user is present. `isUserLoading`/`isCapabilitiesLoading`
 * avoid flashing the button during the initial `/api/auth/me` /
 * `/api/auth/capabilities` fetches.
 *
 * The `can_execute` pre-check (MISM-291) mirrors the backend relation it
 * approximates — true for the model's owner *or* a holder of the platform-wide
 * `executor` role — client-side, so a caller who would just get a 403 never
 * sees the button at all. This is a UX pre-check only; `create_run` still
 * enforces the real, authoritative `_assert_can_execute` check server-side
 * regardless of what this component decides to render.
 */
export function RunControls({ model, scale = 'card' }: RunControlsProps) {
  const isExecutable = Boolean(model.execution_type);
  const launchModal = useDisclosure();
  const { user, isLoading: isUserLoading } = useUser();
  const { capabilities, isLoading: isCapabilitiesLoading } = useCapabilities();
  const canExecute = user?.sub === model.owner || capabilities.executor;

  if (
    !isExecutable ||
    isUserLoading ||
    isCapabilitiesLoading ||
    !user ||
    !canExecute
  )
    return null;

  return (
    <>
      {scale === 'card' ? (
        // A tooltip *and* an aria-label: with no visible text, pointer users need
        // the former and assistive tech the latter. `size="sm"` + `isIconOnly`
        // gives a 32px square, matching the bookmark button above it.
        <Tooltip content="Run model" delay={300} closeDelay={100} radius="sm">
          <Button
            isIconOnly
            size="sm"
            color="primary"
            aria-label="Run model"
            className="rounded-lg"
            onPress={launchModal.onOpen}
          >
            <PlayIcon className="size-4" />
          </Button>
        </Tooltip>
      ) : (
        <Button
          size="md"
          color="primary"
          className="px-6 rounded-lg text-[15px] font-bold"
          startContent={<PlayIcon className="size-4" />}
          onPress={launchModal.onOpen}
        >
          Run model
        </Button>
      )}
      {/* Mount only while open so each launch starts from fresh form state. */}
      {launchModal.isOpen && (
        <RunModelModal model={model} isOpen onClose={launchModal.onClose} />
      )}
    </>
  );
}
