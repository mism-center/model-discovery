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
import { Link } from 'react-router';

import {
  isTerminalStatus,
  type ResourceSummaryItem,
  type UserRunItem,
} from '~/api/endpoints/runs';
import type { ArgumentDTO, EntryPointDTO } from '~/api';
import { RunModelModal } from '~/components/sections/search/search-results/run-model-modal';
import { RunOutputFiles } from '~/components/sections/search/search-results/run-output-files';
import { TerminateRunModal } from '~/components/sections/search/search-results/terminate-run-modal';
import {
  formatDuration,
  formatElapsed,
  formatTimestamp,
  STATUS_COLOR,
} from './run-format';

/**
 * Epoch-ms clock that ticks every second while `active`, so a running job's
 * duration counts up on its own instead of freezing until the next run refetch.
 * Returns `null` until mounted on the client — callers fall back to a static
 * duration during SSR/first paint to keep hydration deterministic. The interval
 * is torn down (and never started) once `active` is false, so terminal runs
 * don't keep a timer alive.
 */
function useNow(active: boolean): number | null {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    if (!active) {
      setNow(null);
      return;
    }
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);

  return now;
}

interface RunRowProps {
  /**
   * One row from `UserRunsResponse.runs`: the run record plus its model
   * (full resource summary) and hydrated input/output resources.
   */
  item: UserRunItem;
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

/** Render an argument/parameter value for display. */
function formatArgValue(value: unknown): string {
  if (value == null || value === '') return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/**
 * The entry point a run was launched with, plus the argument values used.
 *
 * For each argument the entry point declares, we show the value the run
 * actually used (`parameters[name]`) when present, otherwise the argument's
 * declared default (tagged "default"). Any `parameters` key that doesn't match
 * a declared argument is listed afterwards so nothing that was sent is hidden.
 */
function EntryPointDetail({
  entrypoint,
  parameters,
}: {
  entrypoint: EntryPointDTO;
  parameters: Record<string, unknown>;
}) {
  const declared: ArgumentDTO[] = entrypoint.arguments ?? [];
  const declaredNames = new Set(declared.map((arg) => arg.name));
  const extraKeys = Object.keys(parameters).filter(
    (key) => !declaredNames.has(key)
  );

  const command = entrypoint.command?.trim() || '—';

  return (
    <div className="flex flex-col gap-2.5">
      <span className={PANEL_LABEL}>Entry point</span>
      <div className="rounded-lg border border-default-200 bg-default-50 px-3.5 py-3">
        <code className="block text-[13px] font-mono text-default-900 wrap-break-word">
          {command}
        </code>
        {entrypoint.purpose && (
          <p className="mt-1 text-xs text-default-600">{entrypoint.purpose}</p>
        )}

        {(declared.length > 0 || extraKeys.length > 0) && (
          <dl className="mt-3 grid grid-cols-[minmax(0,auto)_minmax(0,max-content)_auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 border-t border-default-200/75 pt-3">
            {declared.map((arg) => {
              const overridden = Object.prototype.hasOwnProperty.call(
                parameters,
                arg.name
              );
              const value = overridden
                ? formatArgValue(parameters[arg.name])
                : formatArgValue(arg.default);
              return (
                <div key={arg.name} className="contents">
                  <dt
                    className="text-[13px] font-mono text-default-700 truncate"
                    title={arg.name}
                  >
                    {arg.name}
                  </dt>
                  <dd className="min-w-0 text-[13px] font-mono text-default-900 wrap-break-word">
                    {value}
                  </dd>
                  <span className="self-baseline text-[10px] uppercase tracking-wider text-default-600">
                    {!overridden && value !== '—' ? '(default)' : ''}
                  </span>
                  <span aria-hidden="true" />
                </div>
              );
            })}
            {extraKeys.map((key) => (
              <div key={key} className="contents">
                <dt
                  className="text-[13px] font-mono text-default-700 truncate"
                  title={key}
                >
                  {key}
                </dt>
                <dd className="min-w-0 text-[13px] font-mono text-default-900 wrap-break-word">
                  {formatArgValue(parameters[key])}
                </dd>
                {/* Empty tag + spacer cells keep the value column aligned. */}
                <span aria-hidden="true" />
                <span aria-hidden="true" />
              </div>
            ))}
          </dl>
        )}
      </div>
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

export function RunRow({ item, defaultExpanded = false }: RunRowProps) {
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

  // The parent `/me/runs` query polls (and reconciles active runs server-side)
  // every 5s.
  const run = item.run;
  const outputs: ResourceSummaryItem[] = item.output_resources ?? [];
  const inputs: ResourceSummaryItem[] = item.input_resources ?? [];
  const terminal = isTerminalStatus(run.status);
  const color = STATUS_COLOR[run.status] ?? 'default';

  // Duration shown in the header/detail panel. Terminal runs use the fixed
  // started→completed span. Non-terminal runs count up live from `started_at`
  // (via a 1s clock); before the client clock is ready, or before the job has
  // started, we fall back to the static `0s`-style value so SSR stays stable.
  const now = useNow(!terminal);
  const liveDuration =
    !terminal && now !== null && run.started_at
      ? formatElapsed(run.started_at, now)
      : formatDuration(run.started_at, run.completed_at);

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
          <h3 className="text-base font-bold font-headline text-primary truncate">
            {item.model.name}
          </h3>
          <p className="mt-0.5 flex items-center gap-2 text-[11px] text-default-700">
            <span className="font-mono truncate">{run.id}</span>
            <span aria-hidden="true" className="text-default-500">
              •
            </span>
            <span className="tabular-nums shrink-0">{liveDuration}</span>
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
                  {run.started_at ? liveDuration : '—'}
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

            {run.entrypoint && (
              <EntryPointDetail
                entrypoint={run.entrypoint}
                parameters={run.parameters ?? {}}
              />
            )}

            {terminal && (
              <div className="border-t border-default-200/75 pt-5">
                <RunOutputFiles outputs={outputs} />
              </div>
            )}
          </div>

          {/* Actions bin */}
          <div className="flex items-center justify-end gap-2 px-5 py-3 rounded-b-2xl border-t border-default-200/75 bg-default-50">
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

      {/* Mount only while open so each rerun re-seeds from this run's values. */}
      {rerunModal.isOpen && (
        <RunModelModal
          model={item.model}
          isOpen
          onClose={rerunModal.onClose}
          initialInputResourceIds={run.input_resource_ids}
          initialEntrypointCommand={run.entrypoint?.command}
          initialParameters={run.parameters}
        />
      )}
      <TerminateRunModal
        run={run}
        isOpen={terminateModal.isOpen}
        onClose={terminateModal.onClose}
      />
    </div>
  );
}
