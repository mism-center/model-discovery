import { useEffect, useId, useRef, useState } from 'react';
import cn from 'classnames';
import { Button, Chip, Spinner, useDisclosure } from '@heroui/react';
import {
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  CircleStackIcon,
  ExclamationTriangleIcon,
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
  /**
   * Where this row is being rendered.
   *
   * `'cross-model'` (default) is the My Runs list, where rows span many models
   * and the model name is the row's identity. `'single-model'` is the model
   * detail page, where every row belongs to the model already named in the page
   * header — so the name is repeated noise and "View model" links to the page
   * you are on. In that context the run id becomes the row heading instead.
   */
  context?: 'cross-model' | 'single-model';
  /**
   * Start expanded and scroll into view on mount. Used to reveal a run the
   * user just launched (deep-linked via `?run=<id>` from the launch toast).
   */
  defaultExpanded?: boolean;
}

/** Uppercase section/field label used throughout the expanded panel. */
const PANEL_LABEL =
  'text-[11px] font-bold uppercase tracking-wider text-default-600';

function DetailField({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn('min-w-0', className)}>
      <dt className={PANEL_LABEL}>{label}</dt>
      <dd className="mt-1 text-[13px] text-default-900">{children}</dd>
    </div>
  );
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

export function RunRow({
  item,
  context = 'cross-model',
  defaultExpanded = false,
}: RunRowProps) {
  const singleModel = context === 'single-model';
  const [expanded, setExpanded] = useState(defaultExpanded);
  // Brief attention ring when deep-linked, so the user can see which run the
  // "View" flow landed them on. Fades out after a couple seconds.
  const [highlight, setHighlight] = useState(defaultExpanded);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  // When deep-linked (e.g. from the "View" toast after launching), bring the
  // freshly-opened row into view and briefly ring it.
  useEffect(() => {
    if (!defaultExpanded) return;
    rootRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    const timer = setTimeout(() => setHighlight(false), 2500);
    return () => clearTimeout(timer);
  }, [defaultExpanded]);

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
      ref={rootRef}
      className={cn(
        'rounded-2xl border transition-all duration-500',
        expanded
          ? 'border-slate-200 bg-white shadow-xs'
          : 'border-transparent hover:bg-primary/4',
        highlight && 'ring-1 ring-primary/30'
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
          'outline-none cursor-pointer',
          'focus-visible:ring-2 focus-visible:ring-primary/50',
          expanded
            ? 'rounded-t-2xl bg-primary/2 hover:bg-primary/4 transition-colors'
            : 'rounded-2xl'
        )}
      >
        <div className="min-w-0">
          <h3
            className={cn(
              'truncate text-primary',
              singleModel
                ? 'font-mono text-sm font-semibold'
                : 'text-base font-bold font-headline'
            )}
          >
            {singleModel ? run.id : item.model.name}
          </h3>
          <p className="mt-0.5 flex items-center gap-2 text-[11px] text-default-700">
            {!singleModel && (
              <>
                <span className="font-mono truncate">{run.id}</span>
                <span aria-hidden="true" className="text-default-500">
                  •
                </span>
              </>
            )}
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
        <div id={panelId} className="border-t border-default-200/75">
          <div className="flex flex-col gap-6 px-5 py-5">
            {/* Details — label-over-value metadata band */}
            <dl className="grid grid-cols-2 gap-x-8 gap-y-4 lg:grid-cols-4">
              <DetailField label="Created">
                <span className="tabular-nums">
                  {formatTimestamp(run.created_at)}
                </span>
              </DetailField>
              <DetailField label="Started">
                <span className="tabular-nums">
                  {formatTimestamp(run.started_at)}
                </span>
              </DetailField>
              <DetailField label="Completed">
                <span className="tabular-nums">
                  {formatTimestamp(run.completed_at)}
                </span>
              </DetailField>
              <DetailField label="Duration">
                <span className="tabular-nums">
                  {terminal
                    ? formatDuration(run.started_at, run.completed_at)
                    : '—'}
                </span>
              </DetailField>
              <DetailField label="Model version">
                {run.model_version ? `v${run.model_version}` : '—'}
              </DetailField>
              <DetailField label="Run ID" className="col-span-2 lg:col-span-3">
                <span className="font-mono text-xs select-all wrap-break-word">
                  {run.id}
                </span>
              </DetailField>
            </dl>

            {run.error_message && (
              <div className="flex gap-3 rounded-lg border border-danger-100 bg-danger-50/60 px-3.5 py-3">
                <ExclamationTriangleIcon
                  aria-hidden="true"
                  className="size-4 shrink-0 mt-0.5 text-danger-500"
                />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-danger-600 uppercase tracking-wider">
                    Error
                  </p>
                  <code className="mt-1 block text-xs text-danger-700 wrap-break-word">
                    {run.error_message}
                  </code>
                </div>
              </div>
            )}

            {inputs.length > 0 && (
              <div className="flex flex-col gap-2.5">
                <span className={PANEL_LABEL}>Inputs</span>
                <ul className="flex flex-wrap gap-2">
                  {inputs.map((resource) => (
                    <li key={resource.id}>
                      <Chip
                        size="sm"
                        variant="flat"
                        className="max-w-60 h-7 bg-default-100 text-default-800"
                        title={resource.name}
                        startContent={
                          <CircleStackIcon className="size-3.5 ml-0.5 text-default-600" />
                        }
                      >
                        <span className="truncate text-xs font-medium">
                          {resource.name}
                        </span>
                      </Chip>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {terminal && (
              <div className="border-t border-default-200/75 pt-5">
                <RunOutputFiles outputs={outputs} />
              </div>
            )}
          </div>

          {/* Actions bin */}
          <div className="flex items-center justify-end gap-2 px-5 py-3 rounded-b-2xl border-t border-default-200/75 bg-default-50">
            {!singleModel && (
              <Button
                as={Link}
                to={`/models/${item.model.id}`}
                size="sm"
                variant="bordered"
                className="font-semibold border-default-300 bg-white text-default-800"
                startContent={<ArrowTopRightOnSquareIcon className="size-4" />}
              >
                View model
              </Button>
            )}
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
