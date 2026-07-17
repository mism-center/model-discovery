import { Button, useDisclosure } from '@heroui/react';
import { PlayIcon } from '@heroicons/react/24/solid';

import type { SearchResultItem } from '~/api';
import { useUser } from '~/api/auth/user';
import { RunModelModal } from './run-model-modal';

interface RunControlsProps {
  model: SearchResultItem;
}

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
export function RunControls({ model }: RunControlsProps) {
  const isExecutable = Boolean(model.execution_type);
  const launchModal = useDisclosure();
  const { user, isLoading: isUserLoading } = useUser();

  if (!isExecutable || isUserLoading || !user) return null;

  return (
    <>
      <Button
        size="sm"
        color="primary"
        className="px-5 py-2.5 rounded-lg text-sm font-bold"
        startContent={<PlayIcon className="size-4" />}
        onPress={launchModal.onOpen}
      >
        Run model
      </Button>
      <RunModelModal
        model={model}
        isOpen={launchModal.isOpen}
        onClose={launchModal.onClose}
      />
    </>
  );
}
