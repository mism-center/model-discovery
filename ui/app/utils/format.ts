/**
 * Format an ISO timestamp / date string as `Mon Year` (e.g. `Jan 2024`).
 * Falls back to the raw input for unparseable values.
 */
export function formatMonthYear(iso: string): string {
  const date = parseLoose(iso);
  if (!date) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    year: 'numeric',
    // Pin the zone for date-only values. Without this, `new Date('2024-01-01')`
    // is parsed as UTC midnight and then rendered in the viewer's local zone, so
    // anyone west of Greenwich sees "Dec 2023" — and the server (UTC) and client
    // disagree, which React 19 reports as a hydration mismatch.
    timeZone: isDateOnly(iso) ? 'UTC' : undefined,
  }).format(date);
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function isDateOnly(value: string): boolean {
  return DATE_ONLY.test(value.trim());
}

function parseLoose(value: string): Date | undefined {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? undefined : date;
}

/**
 * Decimal, so the labels below are honest: a KB is 1000 bytes, not 1024.
 *
 * This used to divide by 1024 while labelling the result KB/MB, which named
 * neither convention and understated every size by ~2.4% per magnitude.
 * Decimal is what Finder, browser download managers and drive capacities
 * report, so a size shown here matches what the file looks like once it lands.
 * Dividing by 1024 would be equally valid, but only with KiB/MiB labels.
 */
const BYTE_UNIT = 1000;

/**
 * Human-readable byte-size formatting (e.g. `1.5 MB`).
 */
export function formatBytes(bytes: number): string {
  if (bytes < BYTE_UNIT) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / BYTE_UNIT;
  let i = 0;
  while (value >= BYTE_UNIT && i < units.length - 1) {
    value /= BYTE_UNIT;
    i++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
}
