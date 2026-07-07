import { Button, useDisclosure } from '@heroui/react';
import { PlayIcon } from '@heroicons/react/24/solid';
import { useQuery } from '@tanstack/react-query';

import { pickActiveRun, type SearchResultItem } from '~/api';
import { modelRunsQueryOptions } from '~/api/query/runs';
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
 * "Owned" means launched by the current authenticated user. The server stamps
 * each run's `triggered_by` with the caller's identity (the OIDC `sub`), so we
 * filter the model's run history down to runs whose `triggered_by` matches the
 * signed-in user's `sub`.
 *
 * Each executable card fetches its own run history on mount so the chip
 * appears immediately when an active run exists. React Query dedupes and
 * caches per-model so this is cheap on rerender / repagination.
 *
 * `pickActiveRun` accepts a predicate so this can later narrow further (e.g.
 * "active *batch* run") once interactive runs become independently trackable.
 */
export function RunControls({ model }: RunControlsProps) {
  const isExecutable = Boolean(model.execution_type);
  const launchModal = useDisclosure();
  const { user, isLoading: isUserLoading } = useUser();

  const runsQuery = useQuery({
    ...modelRunsQueryOptions(model.id),
    enabled: isExecutable && Boolean(user),
  });

  if (!isExecutable) return null;

  // Running is an authenticated action — the server rejects anonymous launches
  // and there's no identity to scope run history to, so render nothing until a
  // user is present. `isUserLoading` avoids flashing anything during the
  // initial `/api/auth/me` fetch.
  if (isUserLoading || !user) return null;

  const ownedActiveRun = pickActiveRun(
    runsQuery.data?.runs,
    (run) => run.triggered_by === user.sub
  );

  if (ownedActiveRun) {
    return <RunStatusPopover initialRun={ownedActiveRun.run} model={model} />;
  }

  // While the initial fetch is in flight, render a disabled button rather
  // than a primary "Run model" — otherwise we'd briefly show the launch
  // affordance for a model that already has an owned active run.
  const isInitialLoading = runsQuery.isLoading;

  return (
    <>
      <Button
        size="sm"
        color="primary"
        className="px-5 py-2.5 rounded-lg text-sm font-bold"
        startContent={
          isInitialLoading ? undefined : <PlayIcon className="size-4" />
        }
        onPress={launchModal.onOpen}
        isLoading={isInitialLoading}
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
