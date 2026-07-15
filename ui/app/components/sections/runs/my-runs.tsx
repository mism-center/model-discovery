import { useEffect, useMemo, useState, useTransition } from 'react';
import cn from 'classnames';
import {
  BreadcrumbItem,
  Button,
  Input,
  Skeleton,
  Tab,
  Tabs,
} from '@heroui/react';
import { MagnifyingGlassIcon } from '@heroicons/react/16/solid';
import { ArrowRightIcon, RocketLaunchIcon } from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';

import type { UserRunItem } from '~/api/endpoints/runs';
import { userRunsQueryOptions } from '~/api/query/runs';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { CompactBreadcrumbs } from '~/components/layout/breadcrumbs';
import { RunRow } from './run-row';
import { RunsSidebar } from './runs-sidebar';
import {
  activeFilterCount,
  applyFilters,
  parseRunFilters,
  STATUS_VALUES,
} from './run-filters';

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
  filtered,
  clearFilters,
  refetch,
}: {
  error: unknown;
  pending: boolean;
  /** Full run list (before any filter). */
  runs: UserRunItem[];
  /** Runs after all filters are applied. */
  visibleRuns: UserRunItem[];
  /** Whether any filter (status/model/date/outputs/text) is active. */
  filtered: boolean;
  clearFilters: () => void;
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

  // Filters matched nothing — distinct from having no runs at all.
  if (visibleRuns.length === 0 && runs.length > 0 && filtered) {
    return (
      <CenteredState
        icon={MagnifyingGlassIcon}
        title="No matching runs"
        description="No runs match your current filters. Try widening or clearing them."
        action={
          <Button
            size="sm"
            color="primary"
            variant="light"
            className="mt-2 font-semibold"
            onPress={clearFilters}
          >
            Clear filters
          </Button>
        }
      />
    );
  }

  if (runs.length === 0) {
    return (
      <CenteredState
        icon={RocketLaunchIcon}
        title="You haven't run any models yet"
        description="Find an executable model in the catalog and launch it — your runs and their outputs will show up here."
        action={
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
  // Stable per URL so the filter/count memos below actually cache between
  // renders (parseRunFilters builds a fresh object each call). `useSearchParams`
  // returns a stable `searchParams` reference per URL.
  const filters = useMemo(() => parseRunFilters(searchParams), [searchParams]);

  // All filters live in the URL (shareable/refresh-safe). Because filtering is
  // client-side, writing a param must not block the UI — a naive controlled
  // input bound to the URL value stutters while React re-filters the whole list
  // on each keystroke. So: mark param writes as non-urgent transitions (React
  // keeps input/interactions responsive and renders the filtered list in the
  // background), and give the search box its own instant local value that syncs
  // into `?q=` inside the transition.
  const [, startTransition] = useTransition();

  // Mutate a single URL param, preserving the rest.
  const updateParams = (mutate: (next: URLSearchParams) => void) => {
    startTransition(() => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          mutate(next);
          return next;
        },
        { replace: true, preventScrollReset: true }
      );
    });
  };

  const setStatus = (key: string) =>
    updateParams((next) => {
      if (key === 'all') next.delete('status');
      else next.set('status', key);
    });

  // Instant local value for the search box so typing never waits on the
  // client-side re-filter; the URL (`?q=`) syncs inside the transition. Resync
  // when `?q=` changes from elsewhere (clear-all, back/forward navigation).
  const [queryInput, setQueryInput] = useState(filters.q);
  useEffect(() => setQueryInput(filters.q), [filters.q]);

  const setQuery = (value: string) => {
    setQueryInput(value);
    updateParams((next) => {
      if (value) next.set('q', value);
      else next.delete('q');
    });
  };

  const setModels = (models: string[]) =>
    updateParams((next) => {
      next.delete('model');
      for (const id of models) next.append('model', id);
    });

  const setDate = (from: string | undefined, to: string | undefined) =>
    updateParams((next) => {
      if (from) next.set('from', from);
      else next.delete('from');
      if (to) next.set('to', to);
      else next.delete('to');
    });

  const setHasOutputs = (value: boolean) =>
    updateParams((next) => {
      if (value) next.set('outputs', '1');
      else next.delete('outputs');
    });

  const clearFilters = () =>
    updateParams((next) => {
      for (const key of ['status', 'q', 'model', 'from', 'to', 'outputs']) {
        next.delete(key);
      }
    });

  // This route is auth-gated by its loader (`requireUser`), so the component
  // only ever renders for a signed-in user — no signed-out branch needed here.
  // We fetch the full run list once and filter client-side, so status tabs and
  // facets switch instantly and counts are always accurate.
  const { data, isLoading, error, refetch } = useQuery(userRunsQueryOptions());

  const runs = useMemo(() => data?.runs ?? [], [data]);
  const pending = isLoading;

  // Runs after every filter EXCEPT status — the basis for per-status tab counts
  // (each tab count reflects the other active filters).
  const withoutStatus = useMemo(
    () => applyFilters(runs, { ...filters, status: undefined }),
    [runs, filters]
  );
  const visibleRuns = useMemo(
    () => applyFilters(runs, filters),
    [runs, filters]
  );

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: withoutStatus.length };
    for (const s of STATUS_VALUES) counts[s] = 0;
    for (const item of withoutStatus) {
      // Guard against any status the UI doesn't know about so an unexpected
      // value can't turn a tab count into NaN.
      if (item.run.status in counts) counts[item.run.status] += 1;
    }
    return counts;
  }, [withoutStatus]);

  const activeCount = activeFilterCount(filters);
  const filtered = activeCount > 0;

  return (
    <main className="flex flex-col grow">
      <div className="grid grid-cols-[auto_minmax(0,1fr)] grow items-stretch bg-default-50">
        {/* Filter sidebar (hidden on small screens; facets still reachable via the top row) */}
        <aside className="hidden lg:block self-start col-start-1">
          <RunsSidebar
            runs={runs}
            filters={filters}
            onModelsChange={setModels}
            onDateChange={setDate}
            onHasOutputsChange={setHasOutputs}
          />
        </aside>

        {/* Content pane */}
        <section className="col-start-2 lg:border-l border-slate-200 bg-white">
          <div className="flex flex-col w-full grow p-10">
            {/* Header */}
            <div className="mb-6">
              <CompactBreadcrumbs className="mb-3">
                <BreadcrumbItem href="/">Home</BreadcrumbItem>
                <BreadcrumbItem>Run History</BreadcrumbItem>
              </CompactBreadcrumbs>
              <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
                Run History
              </h1>
              <div className="mt-3 flex items-center gap-2.5">
                <span className="text-[16px] font-medium text-default-800/90">
                  Manage and review your latest model executions.
                </span>
              </div>
              {filtered && (
                <div className="mt-3 flex items-center gap-2.5">
                  <span className="text-[15px] font-semibold text-secondary">
                    {visibleRuns.length} of {runs.length}{' '}
                    {runs.length === 1 ? 'run' : 'runs'}
                  </span>
                  {activeCount > 0 && (
                    <Button
                      size="sm"
                      variant="light"
                      color="primary"
                      className="h-6 min-w-0 px-2 text-[13px] font-semibold"
                      onPress={clearFilters}
                    >
                      Clear all
                    </Button>
                  )}
                </div>
              )}
            </div>

            {/* Status tabs + free-text search */}
            <div className="flex flex-col sm:flex-row sm:items-end gap-3 sm:gap-4 mb-4 border-b border-default-200/75">
              {/* Own scroll region so a narrow viewport scrolls the tab list
                  instead of clipping the right-most tabs out of reach. */}
              <div className="min-w-0 grow overflow-x-auto">
                <Tabs
                  aria-label="Filter runs by status"
                  selectedKey={filters.status ?? 'all'}
                  onSelectionChange={(key) => setStatus(String(key))}
                  variant="underlined"
                  classNames={{
                    base: 'flex',
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
                  <Tab
                    key="all"
                    title={<TabLabel label="All" count={statusCounts.all} />}
                  />
                  {STATUS_VALUES.map((value) => (
                    <Tab
                      key={value}
                      title={
                        <TabLabel
                          label={value[0].toUpperCase() + value.slice(1)}
                          count={statusCounts[value]}
                        />
                      }
                    />
                  ))}
                </Tabs>
              </div>

              <Input
                aria-label="Search your runs"
                placeholder="Search runs…"
                value={queryInput}
                onValueChange={setQuery}
                isClearable
                onClear={() => setQuery('')}
                radius="none"
                className="w-full sm:w-72 sm:shrink-0 mb-3"
                classNames={{
                  input: 'text-[13px]',
                  inputWrapper: cn(
                    'min-h-8 h-8',
                    'bg-white! border border-default-300 shadow-none rounded-md',
                    'hover:border-default-500',
                    'focus-within:border-default-600! focus-within:ring-2 focus-within:ring-default-200',
                    'transition-all duration-200'
                  ),
                }}
                startContent={
                  <MagnifyingGlassIcon className="size-4 text-slate-400 mr-1" />
                }
              />
            </div>

            {/* Body */}
            <MyRunsBody
              error={error}
              pending={pending}
              runs={runs}
              visibleRuns={visibleRuns}
              filtered={filtered}
              clearFilters={clearFilters}
              refetch={refetch}
            />
          </div>
        </section>
      </div>
    </main>
  );
}

function TabLabel({ label, count }: { label: string; count: number }) {
  return (
    <span className="flex items-center gap-3">
      {label}
      <span className="text-sm font-bold text-default-700/75">{count}</span>
    </span>
  );
}
