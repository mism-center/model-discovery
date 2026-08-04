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
 * Human-readable byte-size formatting (e.g. `1.5 MB`).
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
}
