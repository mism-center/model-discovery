import { Button, Tooltip, useDisclosure } from '@heroui/react';
import { PlayIcon } from '@heroicons/react/24/solid';

import type { RunnableModel } from '~/api/endpoints/runs';
import { useUser } from '~/api/auth/user';
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
 *   - executable + signed in + no can_execute → disabled button with tooltip
 *   - non-executable or signed out → render nothing
 *
 * Running is an authenticated action — the server rejects anonymous launches —
 * so nothing renders until a user is present. `isUserLoading` avoids flashing
 * the button during the initial `/api/auth/me` fetch.
 *
 * `can_execute` comes from the server (OpenFGA batch check stamped onto the
 * search/detail response) so the UI never approximates it client-side.
 * `create_run` still enforces the authoritative `assert_can_execute` check
 * server-side regardless of what this component renders.
 */
export function RunControls({ model, scale = 'card' }: RunControlsProps) {
  const isExecutable = Boolean(model.execution_type);
  const launchModal = useDisclosure();
  const { user, isLoading: isUserLoading } = useUser();
  const canExecute = model.can_execute ?? false;

  if (!isExecutable || isUserLoading || !user) return null;

  const isCard = scale === 'card';
  // Page + enabled is the only case that needs no tooltip (button has a visible label).
  const enabledTooltip = isCard ? 'Run model' : null;
  const tooltipContent = canExecute
    ? enabledTooltip
    : "You don't have permission to run this model";
  // Card buttons are icon-only; aria-label is their sole accessible name.
  const cardAriaLabel = canExecute
    ? 'Run model'
    : 'Run model (permission required)';

  const button = (
    <Button
      isIconOnly={isCard}
      size={isCard ? 'sm' : 'md'}
      color="primary"
      isDisabled={!canExecute}
      aria-label={isCard ? cardAriaLabel : undefined}
      className={
        isCard ? 'rounded-lg' : 'px-6 rounded-lg text-[15px] font-bold'
      }
      startContent={isCard ? undefined : <PlayIcon className="size-4" />}
      onPress={canExecute ? launchModal.onOpen : undefined}
    >
      {isCard ? <PlayIcon className="size-4" /> : 'Run model'}
    </Button>
  );

  return (
    <>
      {tooltipContent == null ? (
        button
      ) : (
        <Tooltip
          content={tooltipContent}
          delay={300}
          closeDelay={100}
          radius="sm"
        >
          {/* Span required when disabled: HeroUI sets pointer-events:none on
              isDisabled buttons, which breaks Tooltip's hover listeners. */}
          {canExecute ? button : <span>{button}</span>}
        </Tooltip>
      )}
      {/* Mount only while open so each launch starts from fresh form state. */}
      {launchModal.isOpen && (
        <RunModelModal model={model} isOpen onClose={launchModal.onClose} />
      )}
    </>
  );
}
