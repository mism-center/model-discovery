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

/**
 * Format a number of seconds as a compact `1h 04m` / `44m 12s` / `8s` string.
 */
export const formatSeconds = (totalSecondsRaw: number): string => {
  const totalSeconds = Math.max(0, Math.round(totalSecondsRaw));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`;
  if (minutes > 0) return `${minutes}m ${String(seconds).padStart(2, '0')}s`;
  return `${seconds}s`;
};

/**
 * Format the elapsed time between two ISO timestamps as a compact `1h 04m` /
 * `44m 12s` / `8s` string. Returns `0s` when either bound is missing or
 * unparseable (e.g. a run that never started, or is still running).
 */
export const formatDuration = (
  start: string | null | undefined,
  end: string | null | undefined
): string => {
  if (!start || !end) return '0s';
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return '0s';
  return formatSeconds((endMs - startMs) / 1000);
};

/**
 * Format the elapsed time from an ISO start up to `nowMs` (epoch ms) as a
 * compact duration string. Used for the live-ticking duration of a still-
 * running job, where there's no `completed_at` to close the interval yet.
 * Returns `0s` when the start is missing or unparseable.
 */
export const formatElapsed = (
  start: string | null | undefined,
  nowMs: number
): string => {
  if (!start) return '0s';
  const startMs = Date.parse(start);
  if (!Number.isFinite(startMs)) return '0s';
  return formatSeconds((nowMs - startMs) / 1000);
};
