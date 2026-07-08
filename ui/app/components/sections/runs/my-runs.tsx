import { useEffect, useMemo, useState } from 'react';
import cn from 'classnames';
import { Button, Input, Skeleton, Tab, Tabs } from '@heroui/react';
import { MagnifyingGlassIcon } from '@heroicons/react/16/solid';
import { ArrowRightIcon, RocketLaunchIcon } from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';
import { matchSorter } from 'match-sorter';
import { Link, useSearchParams } from 'react-router';

import type { RunStatus, UserRunItem } from '~/api/endpoints/runs';
import { userRunsQueryOptions } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { RunRow } from './run-row';

const STATUS_FILTERS: readonly RunStatus[] = [
  'registered',
  'running',
  'completed',
  'failed',
  'cancelled',
];

/** Parse `?status=` — anything but a known RunStatus value means "all". */
function parseStatus(raw: string | null): RunStatus | undefined {
  return raw && (STATUS_FILTERS as readonly string[]).includes(raw)
    ? (raw as RunStatus)
    : undefined;
}

/**
 * Fuzzy-filter runs by a free-text query across the fields a user would search
 * on: model name, run id, notes, and the names of input/output resources.
 * Runs are already status-filtered server-side by `?status=`; this narrows the
 * loaded page client-side (match-sorter, same as the facet sidebar). An empty
 * query returns the list unchanged (order preserved — newest-first from the
 * server).
 */
function filterRuns(runs: UserRunItem[], query: string): UserRunItem[] {
  const q = query.trim();
  if (!q) return runs;
  return matchSorter(runs, q, {
    keys: [
      (item) => item.model.name,
      (item) => item.run.id,
      (item) => item.run.notes,
      (item) => (item.input_resources ?? []).map((r) => r.name),
      (item) => (item.output_resources ?? []).map((r) => r.name),
    ],
  });
}

function RunRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-5 py-4 rounded-2xl border border-transparent">
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <Skeleton className="h-5 w-64 max-w-full rounded-md" />
        <Skeleton className="h-3 w-40 rounded" />
      </div>
      <div className="hidden sm:flex flex-col items-end gap-1.5">
        <Skeleton className="h-3 w-36 rounded" />
        <Skeleton className="h-3 w-32 rounded" />
      </div>
      <Skeleton className="h-6 w-24 rounded-full" />
      <Skeleton className="h-4 w-4 rounded" />
    </div>
  );
}

function CenteredState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center text-center gap-3 py-16">
      <Icon
        className="size-10 text-default-400"
        aria-hidden="true"
        strokeWidth={1.25}
      />
      <div className="flex flex-col gap-1 max-w-sm">
        <h3 className="text-base font-semibold text-default-900">{title}</h3>
        <p className="text-sm text-default-600 leading-relaxed">
          {description}
        </p>
      </div>
      {action}
    </div>
  );
}

function MyRunsBody({
  error,
  pending,
  runs,
  visibleRuns,
  query,
  clearQuery,
  status,
  setStatus,
  refetch,
}: {
  error: unknown;
  pending: boolean;
  /** Runs after the server-side status filter, before the client-side query. */
  runs: UserRunItem[];
  /** Runs after the client-side search query is applied. */
  visibleRuns: UserRunItem[];
  query: string;
  clearQuery: () => void;
  status: RunStatus | undefined;
  setStatus: (key: string) => void;
  refetch: () => void;
}) {
  if (error) {
    return (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load your runs"
        onRetry={refetch}
      />
    );
  }

  if (pending) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <RunRowSkeleton key={i} />
        ))}
      </div>
    );
  }

  // A search query that matches nothing — distinct from having no runs at all.
  if (visibleRuns.length === 0 && runs.length > 0 && query.trim()) {
    return (
      <CenteredState
        icon={MagnifyingGlassIcon}
        title="No matching runs"
        description={`No runs match “${query.trim()}”. Try a different model name, run id, or resource.`}
        action={
          <Button
            size="sm"
            color="primary"
            variant="light"
            className="mt-2 font-semibold"
            onPress={clearQuery}
          >
            Clear search
          </Button>
        }
      />
    );
  }

  if (runs.length === 0) {
    return (
      <CenteredState
        icon={RocketLaunchIcon}
        title={status ? `No ${status} runs` : "You haven't run any models yet"}
        description={
          status
            ? 'No runs match this status filter.'
            : 'Find an executable model in the catalog and launch it — your runs and their outputs will show up here.'
        }
        action={
          status ? (
            <Button
              size="sm"
              color="primary"
              variant="light"
              className="mt-2 font-semibold"
              onPress={() => setStatus('all')}
            >
              Show all runs
            </Button>
          ) : (
            <Button
              as={Link}
              to="/search"
              size="sm"
              color="primary"
              className="mt-2 font-semibold"
              endContent={<ArrowRightIcon className="size-4" />}
            >
              Browse models
            </Button>
          )
        }
      />
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {visibleRuns.map((item) => (
        <li key={item.run.id}>
          <RunRow item={item} />
        </li>
      ))}
    </ul>
  );
}

export default function MyRunsSection() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = parseStatus(searchParams.get('status'));
  const query = searchParams.get('q') ?? '';

  const setStatus = (key: string) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (key === 'all') next.delete('status');
        else next.set('status', key);
        return next;
      },
      { replace: true, preventScrollReset: true }
    );
  };

  const setQuery = (value: string) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set('q', value);
        else next.delete('q');
        return next;
      },
      { replace: true, preventScrollReset: true }
    );
  };

  // Local input value so typing stays snappy; mirror it to the shareable `?q=`
  // URL param, and keep it in sync when the param changes elsewhere (e.g. the
  // "Clear search" action or back/forward navigation).
  const [queryInput, setQueryInput] = useState(query);
  useEffect(() => setQueryInput(query), [query]);

  const onQueryChange = (value: string) => {
    setQueryInput(value);
    setQuery(value);
  };

  // This route is auth-gated by its loader (`requireUser`), so the component
  // only ever renders for a signed-in user — no signed-out branch needed here.
  const { data, isLoading, error, refetch } = useQuery(
    userRunsQueryOptions(status)
  );

  const runs = data?.runs ?? [];
  const total = data?.total;
  const pending = isLoading;

  const visibleRuns = useMemo(
    () => filterRuns(runs, queryInput),
    [runs, queryInput]
  );

  // Count summary: while searching, show "N of M"; otherwise just the total.
  let countLabel = 'Your run history across all models.';
  if (total !== undefined) {
    const noun = total === 1 ? 'run' : 'runs';
    countLabel = queryInput.trim()
      ? `${visibleRuns.length} of ${total} ${noun}`
      : `${total} ${noun}`;
  }

  return (
    <section className="flex flex-col w-full max-w-5xl mx-auto grow p-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
          My Runs
        </h1>
        <p className="mt-3 text-[16px] font-medium text-default-800/90">
          {countLabel}
          {total !== undefined && status && (
            <>
              {' '}
              with status{' '}
              <span className="text-secondary font-bold capitalize">
                {status}
              </span>
            </>
          )}
        </p>
      </div>

      {/* Filters: status tabs + free-text search */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-3 sm:gap-4 mb-4 border-b border-default-200/75">
        <Tabs
          aria-label="Filter runs by status"
          selectedKey={status ?? 'all'}
          onSelectionChange={(key) => setStatus(String(key))}
          variant="underlined"
          classNames={{
            base: 'flex grow',
            tabList: 'p-0 gap-0',
            tab: cn(
              'w-auto pt-0 pb-4 px-5 h-9',
              'border-b-2 border-transparent data-[selected=true]:border-primary',
              'hover:text-primary',
              'opacity-100! active:opacity-80!',
              'transition-all duration-200'
            ),
            tabContent: cn(
              'text-[15px] font-extrabold text-default-800/90 group-data-[selected=true]:text-primary',
              'group-hover:text-primary/85'
            ),
            cursor: 'hidden',
          }}
        >
          <Tab key="all" title="All" />
          {STATUS_FILTERS.map((value) => (
            <Tab
              key={value}
              title={<span className="capitalize">{value}</span>}
            />
          ))}
        </Tabs>

        <Input
          aria-label="Search your runs"
          placeholder="Search runs…"
          value={queryInput}
          onValueChange={onQueryChange}
          isClearable
          onClear={() => onQueryChange('')}
          size="sm"
          variant="bordered"
          className="sm:w-72 shrink-0 mb-3"
          startContent={
            <MagnifyingGlassIcon className="size-4 text-default-500 shrink-0" />
          }
        />
      </div>

      {/* Body */}
      <MyRunsBody
        error={error}
        pending={pending}
        runs={runs}
        visibleRuns={visibleRuns}
        query={queryInput}
        clearQuery={() => onQueryChange('')}
        status={status}
        setStatus={setStatus}
        refetch={refetch}
      />
    </section>
  );
}
