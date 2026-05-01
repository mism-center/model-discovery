import { Button, Spinner, Tooltip, useDisclosure } from '@heroui/react';
import { ArrowPathIcon } from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';

import {
  isTerminalStatus,
  type RunDetailItem,
  type SearchResultItem,
} from '~/api';
import { runDetailQueryOptions } from '~/api/query/runs';
import { RunModelModal } from './run-model-modal';
import { RunOutputFiles } from './run-output-files';
import { TerminateRunModal } from './terminate-run-modal';

interface RunStatusPopoverProps {
  /** The run we know about from the model-runs query. May be stale. */
  initialRun: RunDetailItem;
  /** Needed so a terminal run's "Rerun" can open the launch modal. */
  model: SearchResultItem;
  /** Forwarded to the launch modal for the rerun request. */
  triggeredBy: string;
}

const STATUS_COLOR: Record<
  string,
  'default' | 'primary' | 'success' | 'danger' | 'warning' | 'secondary'
> = {
  registered: 'warning',
  running: 'secondary',
  completed: 'success',
  failed: 'danger',
  cancelled: 'default',
};

const formatTimestamp = (iso: string | null | undefined): string => {
  if (!iso) return '—';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return iso;
  return new Date(ms).toLocaleString();
};

export function RunStatusPopover({
  initialRun,
  model,
  triggeredBy,
}: RunStatusPopoverProps) {
  const { data } = useQuery({
    ...runDetailQueryOptions(initialRun.id),
    initialData: { run: initialRun },
  });

  const run = data?.run ?? initialRun;
  const outputs = data?.output_resources ?? [];
  const terminal = isTerminalStatus(run.status);
  const color = STATUS_COLOR[run.status] ?? 'default';
  const rerunModal = useDisclosure();
  const terminateModal = useDisclosure();

  return (
    <>
      <Tooltip
        delay={80}
        closeDelay={150}
        showArrow
        placement="bottom-end"
        content={
          <div className="flex flex-col gap-3 p-3 min-w-70">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-primary">
                Run status
              </span>
            </div>

            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
              <dt className="text-default-600">Run ID</dt>
              <dd className="font-mono wrap-break-word">{run.id}</dd>

              <dt className="text-default-600">Created</dt>
              <dd>{formatTimestamp(run.created_at)}</dd>

              <dt className="text-default-600">Started</dt>
              <dd>{formatTimestamp(run.started_at)}</dd>

              {terminal && (
                <>
                  <dt className="text-default-600">Completed</dt>
                  <dd>{formatTimestamp(run.completed_at)}</dd>
                </>
              )}

              {run.error_message && (
                <>
                  <dt className="text-default-600">Error</dt>
                  <dd className="wrap-break-word">
                    <code>{run.error_message}</code>
                  </dd>
                </>
              )}
            </dl>

            {terminal && <RunOutputFiles outputs={outputs} />}

            {terminal ? (
              <Button
                size="sm"
                color="primary"
                variant="solid"
                className="w-full font-semibold mt-1"
                startContent={<ArrowPathIcon className="size-4" />}
                onPress={rerunModal.onOpen}
              >
                Rerun
              </Button>
            ) : (
              <Button
                size="sm"
                color="danger"
                variant="solid"
                className="w-full font-semibold text-white mt-1"
                onPress={terminateModal.onOpen}
              >
                Terminate run
              </Button>
            )}
          </div>
        }
      >
        <Button
          size="sm"
          color={color}
          className={`px-5 py-2.5 rounded-lg text-sm font-bold capitalize ${run.status === 'completed' && 'opacity-75'}`}
          startContent={
            terminal ? (
              <ArrowPathIcon className="size-4" />
            ) : (
              <Spinner
                size="sm"
                color="white"
                classNames={{ wrapper: 'w-4 h-4' }}
              />
            )
          }
        >
          {run.status}
        </Button>
      </Tooltip>
      <RunModelModal
        model={model}
        triggeredBy={triggeredBy}
        isOpen={rerunModal.isOpen}
        onClose={rerunModal.onClose}
        initialInputResourceIds={run.input_resource_ids}
      />
      <TerminateRunModal
        run={run}
        isOpen={terminateModal.isOpen}
        onClose={terminateModal.onClose}
      />
    </>
  );
}
