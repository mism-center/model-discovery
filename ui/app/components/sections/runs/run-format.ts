/**
 * Shared presentation helpers for run status + timestamps.
 *
 * These are the canonical versions of the STATUS_COLOR map and
 * formatTimestamp helper that also appear inline in
 * `search-results/run-status-popover.tsx` — new run UI should import from
 * here so both surfaces stay in sync.
 */

export type StatusColor =
  | 'default'
  | 'primary'
  | 'success'
  | 'danger'
  | 'warning'
  | 'secondary';

/** HeroUI semantic color for each RunStatus value (lowercase enum .value). */
export const STATUS_COLOR: Record<string, StatusColor> = {
  registered: 'warning',
  running: 'secondary',
  completed: 'success',
  failed: 'danger',
  cancelled: 'default',
};

/**
 * Format an ISO datetime as a locale-aware string. Nullish or unparseable
 * values render as an em dash / the raw value respectively.
 */
export const formatTimestamp = (iso: string | null | undefined): string => {
  if (!iso) return '—';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return iso;
  return new Date(ms).toLocaleString();
};
