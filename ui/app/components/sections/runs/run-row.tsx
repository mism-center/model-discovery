import { useId, useState } from 'react';
import cn from 'classnames';
import { Button, Chip, Spinner, useDisclosure } from '@heroui/react';
import {
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  NoSymbolIcon,
  StopIcon,
  XCircleIcon,
} from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';

import {
  isTerminalStatus,
  type ResourceSummaryItem,
  type UserRunItem,
} from '~/api/endpoints/runs';
import { runDetailQueryOptions } from '~/api/query/runs';
import { RunModelModal } from '~/components/sections/search/search-results/run-model-modal';
import { RunOutputFiles } from '~/components/sections/search/search-results/run-output-files';
import { TerminateRunModal } from '~/components/sections/search/search-results/terminate-run-modal';
import { formatDuration, formatTimestamp, STATUS_COLOR } from './run-format';

interface RunRowProps {
  /**
   * One row from `UserRunsResponse.runs`: the run record plus its model
   * (full resource summary) and hydrated input/output resources.
   */
  item: UserRunItem;
}

function StatusIcon({ status }: { status: string }) {
  if (!isTerminalStatus(status)) {
    return (
      <Spinner
        size="sm"
        color="current"
        classNames={{ wrapper: 'w-3.5 h-3.5' }}
      />
    );
  }
  if (status === 'failed') return <XCircleIcon className="size-3.5" />;
  if (status === 'cancelled') return <NoSymbolIcon className="size-3.5" />;
  return <CheckCircleIcon className="size-3.5" />;
}

export function RunRow({ item }: RunRowProps) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();

  // Live run detail (status refresh + hydrated outputs). Seeded from the list
  // item so nothing fetches until the row is expanded; once expanded, the
  // options' backed-off polling keeps non-terminal runs fresh and stops at a
  // terminal status. (Same seeding pattern as run-status-popover.)
  const { data } = useQuery({
    ...runDetailQueryOptions(item.run.id),
    initialData: {
      run: item.run,
      input_resources: item.input_resources,
      output_resources: item.output_resources,
    },
    enabled: expanded,
  });

  const run = data?.run ?? item.run;
  const outputs: ResourceSummaryItem[] =
    data?.output_resources ?? item.output_resources ?? [];
  const inputs: ResourceSummaryItem[] =
    data?.input_resources ?? item.input_resources ?? [];
  const terminal = isTerminalStatus(run.status);
  const color = STATUS_COLOR[run.status] ?? 'default';

  const rerunModal = useDisclosure();
  const terminateModal = useDisclosure();

  return (
    <div
      className={cn(
        'rounded-2xl border transition-colors duration-200',
        expanded
          ? 'border-slate-200 bg-primary/2'
          : 'border-transparent hover:bg-primary/4'
      )}
    >
      {/* Collapsed header — the whole strip toggles the detail panel. */}
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={() => setExpanded((open) => !open)}
        className={cn(
          // Grid (not flex) with fixed tracks so the timestamp and status
          // columns start at the same x-position on every row, like a table.
          // On <sm the timestamp track collapses to 0 (that column is hidden).
          'grid w-full items-center gap-4 px-5 py-4 text-left',
          'grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,1fr)_13rem_9rem]',
          'rounded-2xl outline-none cursor-pointer',
          'focus-visible:ring-2 focus-visible:ring-primary/50'
        )}
      >
        <div className="min-w-0">
          <h3 className="text-base font-bold font-headline text-primary truncate">
            {item.model.name}
          </h3>
          <p className="mt-0.5 flex items-center gap-2 text-[11px] text-default-700">
            <span className="font-mono truncate">{run.id}</span>
            <span aria-hidden="true" className="text-default-500">
              •
            </span>
            <span className="tabular-nums shrink-0">
              {formatDuration(run.started_at, run.completed_at)}
            </span>
            <span aria-hidden="true" className="text-default-500">
              •
            </span>
            <span className="shrink-0">
              {outputs.length} out / {inputs.length} in
            </span>
          </p>
        </div>

        {/* Left-aligned label/value columns; the parent grid pins this track to
            a fixed width so timestamps line up across rows. */}
        <dl
          className={cn(
            'hidden sm:grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5',
            'text-[11px] text-default-800 uppercase tracking-tight'
          )}
        >
          <dt className="text-default-600">Created</dt>
          <dd className="tabular-nums">{formatTimestamp(run.created_at)}</dd>
          <dt className="text-default-600">Started</dt>
          <dd className="tabular-nums">{formatTimestamp(run.started_at)}</dd>
        </dl>

        <div className="flex items-center justify-end gap-5">
          <Chip
            size="sm"
            color={color}
            variant="flat"
            className="capitalize font-bold px-2 h-7"
            startContent={
              <div className="mr-1.5">
                <StatusIcon status={run.status} />
              </div>
            }
          >
            {run.status}
          </Chip>

          <ChevronDownIcon
            aria-hidden="true"
            className={cn(
              'size-4 shrink-0 text-default-600 transition-transform duration-200',
              expanded && 'rotate-180'
            )}
          />
        </div>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div
          id={panelId}
          className="flex flex-col gap-5 px-5 pb-5 pt-1 border-t border-default-200/75"
        >
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs pt-3">
            <dt className="text-default-700">Model</dt>
            <dd>
              {item.model.name}
              {run.model_version && (
                <span className="ml-2 text-default-700">
                  (v{run.model_version})
                </span>
              )}
            </dd>

            <dt className="text-default-700">Run ID</dt>
            <dd className="font-mono wrap-break-word">{run.id}</dd>

            <dt className="text-default-700">Created</dt>
            <dd className="tabular-nums">{formatTimestamp(run.created_at)}</dd>

            <dt className="text-default-700">Started</dt>
            <dd className="tabular-nums">{formatTimestamp(run.started_at)}</dd>

            {terminal && (
              <>
                <dt className="text-default-700">Completed</dt>
                <dd>{formatTimestamp(run.completed_at)}</dd>
              </>
            )}

            {run.error_message && (
              <>
                <dt className="text-default-600">Error</dt>
                <dd className="wrap-break-word text-danger">
                  <code>{run.error_message}</code>
                </dd>
              </>
            )}
          </dl>

          {inputs.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-primary">
                Inputs
              </span>
              <ul className="flex flex-wrap gap-2">
                {inputs.map((resource) => (
                  <li key={resource.id}>
                    <Chip
                      size="sm"
                      variant="bordered"
                      className="max-w-60 text-xs"
                      title={resource.name}
                    >
                      <span className="truncate">{resource.name}</span>
                    </Chip>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {terminal && <RunOutputFiles outputs={outputs} />}

          <div className="flex justify-end gap-2 mt-1">
            <Button
              as={Link}
              to={`/models/${item.model.id}`}
              size="sm"
              className="font-semibold bg-default-300"
              startContent={<ArrowTopRightOnSquareIcon className="size-4" />}
            >
              View model
            </Button>
            {terminal ? (
              <Button
                size="sm"
                color="primary"
                variant="solid"
                className="font-semibold"
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
                className="font-semibold text-white"
                startContent={<StopIcon className="size-4" />}
                onPress={terminateModal.onOpen}
              >
                Abort
              </Button>
            )}
          </div>
        </div>
      )}

      <RunModelModal
        model={item.model}
        isOpen={rerunModal.isOpen}
        onClose={rerunModal.onClose}
        initialInputResourceIds={run.input_resource_ids}
      />
      <TerminateRunModal
        run={run}
        isOpen={terminateModal.isOpen}
        onClose={terminateModal.onClose}
      />
    </div>
  );
}
