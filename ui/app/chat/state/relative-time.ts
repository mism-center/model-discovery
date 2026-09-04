const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;
const MONTH = 30 * DAY;
const YEAR = 365 * DAY;

const UNITS: [threshold: number, unit: Intl.RelativeTimeFormatUnit][] = [
  [YEAR, 'year'],
  [MONTH, 'month'],
  [WEEK, 'week'],
  [DAY, 'day'],
  [HOUR, 'hour'],
  [MINUTE, 'minute'],
];

const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

/** "3 minutes ago", "yesterday", "2 weeks ago". */
export function timeAgo(timestamp: number, now: number): string {
  const elapsed = now - timestamp;
  for (const [threshold, unit] of UNITS) {
    if (elapsed >= threshold) {
      return formatter.format(-Math.floor(elapsed / threshold), unit);
    }
  }
  return 'just now';
}
