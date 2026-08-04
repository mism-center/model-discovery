import { Button, useDisclosure } from '@heroui/react';
import { PlayIcon } from '@heroicons/react/24/solid';

import type { RunnableModel } from '~/api/endpoints/runs';
import { useUser } from '~/api/auth/user';
import { RunModelModal } from './run-model-modal';

interface RunControlsProps {
  model: RunnableModel;
  /**
   * Visual scale of the launch button.
   *
   * `'card'` (the default) is the original row-action sizing used by search
   * results. `'page'` is for the detail page, where this is the page's primary
   * verb sitting beside a `text-3xl` heading — at card scale it read as an
   * incidental row action. Defaulted so the search page is untouched.
   */
  scale?: 'card' | 'page';
}

const SCALES = {
  card: {
    size: 'sm' as const,
    className: 'px-5 py-2.5 rounded-lg text-sm font-bold',
  },
  page: {
    size: 'md' as const,
    className: 'px-6 rounded-lg text-[15px] font-bold',
  },
};

/**
 * Launch affordance for an executable model in the search results.
 *
 * Live run status and outputs now live on the "My Runs" page, so the card only
 * offers the launch action:
 *
 *   - executable + signed in → `Run model` button (opens the launch modal)
 *   - non-executable or signed out → render nothing
 *
 * Running is an authenticated action — the server rejects anonymous launches —
 * so nothing renders until a user is present. `isUserLoading` avoids flashing
 * the button during the initial `/api/auth/me` fetch.
 */
export function RunControls({ model, scale = 'card' }: RunControlsProps) {
  const isExecutable = Boolean(model.execution_type);
  const launchModal = useDisclosure();
  const { user, isLoading: isUserLoading } = useUser();

  if (!isExecutable || isUserLoading || !user) return null;

  const { size, className } = SCALES[scale];

  return (
    <>
      <Button
        size={size}
        color="primary"
        className={className}
        startContent={<PlayIcon className="size-4" />}
        onPress={launchModal.onOpen}
      >
        Run model
      </Button>
      {/* Mount only while open so each launch starts from fresh form state. */}
      {launchModal.isOpen && (
        <RunModelModal model={model} isOpen onClose={launchModal.onClose} />
      )}
    </>
  );
}
