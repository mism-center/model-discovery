import type { CalendarDate } from '@internationalized/date';

// Convert internationalized/date's `CalendarDate` to days elapsed since start of epoch time.
export function toDayNumber(date: CalendarDate): number {
  // CalendarDate.month is 1-indexed
  const jsDate = new Date(date.year, date.month - 1, date.day);
  return Math.floor(jsDate.getTime() / (24 * 60 * 60 * 1000));
}
