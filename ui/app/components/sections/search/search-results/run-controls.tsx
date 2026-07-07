import { Button, useDisclosure } from '@heroui/react';
import { PlayIcon } from '@heroicons/react/24/solid';
import { useQuery } from '@tanstack/react-query';

import { pickActiveRun, type SearchResultItem } from '~/api';
import { ownedModelRunsQueryOptions } from '~/api/query/runs';
import { useUser } from '~/api/auth/user';
import { RunModelModal } from './run-model-modal';
import { RunStatusPopover } from './run-status-popover';

interface RunControlsProps {
  model: SearchResultItem;
}

/**
 * Per-card run state machine:
 *
 *   - executable + no owned active run → `Run model` button (opens launch modal)
 *   - executable + owned active run    → status chip with details popover
 *   - non-executable                   → render nothing
 *
 * "Owned" means launched by the current authenticated user. The search
 * endpoint embeds the caller's own runs per executable model as
 * `model.owned_runs` (the server scopes them by the authenticated `sub`), so
 * the card renders without a per-model request. We seed the owned-runs query
 * with that embedded data; a launch invalidates the query to pull the fresh
 * run in, so the chip stays live after the initial paint.
 */
export function RunControls({ model }: RunControlsProps) {
  const isExecutable = Boolean(model.execution_type);
  const launchModal = useDisclosure();
  const { user, isLoading: isUserLoading } = useUser();

  const runsQuery = useQuery({
    ...ownedModelRunsQueryOptions(model.id),
    // Embedded from the search response — no fetch on first render.
    initialData: model.owned_runs,
    enabled: isExecutable && Boolean(user),
  });

  if (!isExecutable) return null;

  // Running is an authenticated action — the server rejects anonymous launches
  // and there's no identity to scope run history to, so render nothing until a
  // user is present. `isUserLoading` avoids flashing anything during the
  // initial `/api/auth/me` fetch.
  if (isUserLoading || !user) return null;

  const ownedActiveRun = pickActiveRun(runsQuery.data);

  if (ownedActiveRun) {
    return <RunStatusPopover initialRun={ownedActiveRun} model={model} />;
  }

  // No active owned run — the run history was embedded in the search response
  // (initialData), so there's no initial fetch to wait on: show the launch
  // affordance directly.
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
