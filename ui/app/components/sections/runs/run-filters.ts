import { matchSorter } from 'match-sorter';

import type { RunStatus, UserRunItem } from '~/api/endpoints/runs';

export const STATUS_VALUES: readonly RunStatus[] = [
  'registered',
  'running',
  'completed',
  'failed',
  'cancelled',
];

export interface RunFilters {
  /** `?status=` — a single RunStatus, or undefined for "all". */
  status?: RunStatus;
  /** `?q=` — free-text query, matched last so it also ranks results. */
  q: string;
  /** `?model=` — repeatable; a run matches if its model is in this set (OR). */
  models: string[];
  /** `?from=` — inclusive lower bound on run.created_at (ISO date, YYYY-MM-DD). */
  from?: string;
  /** `?to=` — inclusive upper bound on run.created_at (ISO date, YYYY-MM-DD). */
  to?: string;
  /** `?outputs=1` — only runs that produced at least one output resource. */
  hasOutputs: boolean;
}

/** Parse `?status=` — anything but a known RunStatus value means "all". */
function parseStatus(raw: string | null): RunStatus | undefined {
  return raw && (STATUS_VALUES as readonly string[]).includes(raw)
    ? (raw as RunStatus)
    : undefined;
}

/** Read the full filter set out of URL search params. */
export function parseRunFilters(sp: URLSearchParams): RunFilters {
  return {
    status: parseStatus(sp.get('status')),
    q: sp.get('q') ?? '',
    models: sp.getAll('model'),
    from: sp.get('from') ?? undefined,
    to: sp.get('to') ?? undefined,
    hasOutputs: sp.get('outputs') === '1',
  };
}

/** How many facets (beyond the always-present status tabs) are active. */
export function activeFilterCount(f: RunFilters): number {
  let n = 0;
  if (f.status) n += 1;
  if (f.q.trim()) n += 1;
  if (f.models.length > 0) n += 1;
  if (f.from || f.to) n += 1;
  if (f.hasOutputs) n += 1;
  return n;
}

const outputsOf = (item: UserRunItem): string[] =>
  item.run.output_resource_ids ?? [];

/**
 * A run's created_at date as a YYYY-MM-DD string, for lexicographic comparison
 * against the `from`/`to` date bounds (ISO dates sort correctly as strings).
 */
function createdDate(item: UserRunItem): string {
  return (item.run.created_at ?? '').slice(0, 10);
}

/**
 * Apply every filter in memory. Pure. Order: status → model → date →
 * hasOutputs → free-text (match-sorter last so it also ranks). All facets AND
 * together; models OR within the group. An empty free-text query preserves the
 * server's newest-first ordering.
 */
export function applyFilters(
  runs: UserRunItem[],
  f: RunFilters
): UserRunItem[] {
  let result = runs;

  if (f.status) {
    result = result.filter((item) => item.run.status === f.status);
  }
  if (f.models.length > 0) {
    const set = new Set(f.models);
    result = result.filter((item) => set.has(item.model.id));
  }
  if (f.from) {
    result = result.filter((item) => createdDate(item) >= f.from!);
  }
  if (f.to) {
    result = result.filter((item) => createdDate(item) <= f.to!);
  }
  if (f.hasOutputs) {
    result = result.filter((item) => outputsOf(item).length > 0);
  }

  const q = f.q.trim();
  if (q) {
    result = matchSorter(result, q, {
      keys: [
        (item) => item.model.name,
        (item) => item.run.id,
        (item) => item.run.notes,
        (item) => (item.input_resources ?? []).map((r) => r.name),
        (item) => (item.output_resources ?? []).map((r) => r.name),
      ],
    });
  }

  return result;
}

export interface ModelBucket {
  id: string;
  name: string;
  count: number;
}

/**
 * Distinct models across the runs, with counts. Counts are computed from the
 * list filtered by everything EXCEPT the model facet, so ticking one model
 * doesn't zero out the others (self-exclusion, matching the search sidebar).
 * Sorted by count desc, then name.
 */
export function modelBuckets(
  runs: UserRunItem[],
  f: RunFilters
): ModelBucket[] {
  const scoped = applyFilters(runs, { ...f, models: [] });
  const byId = new Map<string, ModelBucket>();
  for (const item of scoped) {
    const { id, name } = item.model;
    const existing = byId.get(id);
    if (existing) existing.count += 1;
    else byId.set(id, { id, name, count: 1 });
  }
  // Sorting a fresh array (spread copy), so in-place sort mutates nothing shared.
  // eslint-disable-next-line unicorn/no-array-sort
  const result = [...byId.values()].sort(
    (a, b) => b.count - a.count || a.name.localeCompare(b.name)
  );

  return result;
}
