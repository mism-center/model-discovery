import cn from 'classnames';

/**
 * Uppercase micro-label for a label/value pair.
 *
 * `text-default-800` is load-bearing, not a preference. This project overrides
 * HeroUI's `default` ramp with a light *surface* scale (`ui/app/styles/hero.ts`),
 * so measured against white the ramp reads: 500 = 1.48:1, 600 = 2.19:1,
 * 700 = 3.45:1, 800 = 5.82:1, 900 = 10.36:1. Only 800 and 900 clear WCAG AA, so
 * nothing that renders text may reach below 800.
 */
export const FIELD_LABEL =
  'text-xs font-bold uppercase tracking-wider text-default-800';

/**
 * One label/value pair. Must be rendered inside a `<dl>` for the `<dt>`/`<dd>`
 * to be valid; the wrapping `<div>` is permitted there.
 */
export function DefinitionField({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('min-w-0', className)}>
      <dt className={FIELD_LABEL}>{label}</dt>
      <dd className="mt-1 text-sm text-default-900 break-words">
        {isAbsent(children) ? <NotRecorded /> : children}
      </dd>
    </div>
  );
}

/**
 * Whether an API string field carries a real value.
 *
 * Covers the shapes the API uses for absence, so callers don't each re-derive
 * them:
 *   - `null` / `undefined` — genuinely unset
 *   - `''` — pydantic string fields default to empty rather than null
 *   - `'unknown'` — the sentinel `determinism`, `time_dynamics` and `spatial`
 *     carry when a model has not been characterized (see metadata-schema's
 *     vocabulary). Rendering it verbatim states it as though it were a finding.
 */
export function hasValue(value: string | null | undefined): value is string {
  if (typeof value !== 'string') return false;
  const normalized = value.trim().toLowerCase();
  return normalized !== '' && normalized !== 'unknown';
}

/**
 * Whether a list field carries any entries. The API emits `[]`, not `null`.
 *
 * A type predicate, so `hasItems(model.containers) && model.containers.map(…)`
 * narrows away the `undefined` the generated schema puts on every list field.
 */
export function hasItems<T>(values: T[] | null | undefined): values is T[] {
  return Array.isArray(values) && values.length > 0;
}

function isAbsent(value: React.ReactNode): boolean {
  if (value === null || value === undefined || value === false) return true;
  if (typeof value !== 'string') return false;
  return !hasValue(value);
}

/**
 * States an absence as a fact instead of hiding it, so a field that has no data
 * still says so and assistive tech has something to read. Use for a *single*
 * absent field — a section with nothing at all uses `SectionAbsence` rather
 * than a grid of these.
 */
export function NotRecorded({
  children = 'Not recorded',
}: {
  children?: React.ReactNode;
}) {
  return <span className="text-default-800 italic">{children}</span>;
}
