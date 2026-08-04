import cn from 'classnames';

/**
 * Uppercase micro-label for a label/value pair.
 *
 * `text-default-800` is load-bearing, not a preference. This project overrides
 * HeroUI's `default` ramp with a light *surface* scale (`ui/app/styles/hero.ts`),
 * so measured against white the ramp reads: 500 = 1.48:1, 600 = 2.19:1,
 * 700 = 3.45:1, 800 = 5.82:1, 900 = 10.36:1. Only 800 and 900 clear WCAG AA.
 * Field labels previously used 600 — i.e. 12px uppercase text at 2.19:1 — which
 * is effectively invisible. Nothing that renders text should reach below 800.
 *
 * Sizes come from Tailwind's scale (`text-xs`/`text-sm`) rather than arbitrary
 * `text-[11px]`/`text-[13px]` values, so the page participates in a type scale.
 */
export const FIELD_LABEL =
  'text-xs font-bold uppercase tracking-wider text-default-800';

/**
 * One label/value pair inside a `<dl>`.
 *
 * Consolidates three prior copies of this component: `run-row.tsx`'s
 * `DetailField`/`PANEL_LABEL` and `model-details/primitives.tsx`'s
 * `Field`/`FIELD_LABEL` were character-for-character identical, and the label
 * string was re-typed inline in seven more places.
 *
 * Must be rendered inside a `<dl>` for the `<dt>`/`<dd>` to be valid. The
 * wrapping `<div>` is permitted there — HTML allows `<dt>`/`<dd>` groups to be
 * wrapped in a single `<div>` child of `<dl>`.
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
 * Whether a field value should be treated as "no value recorded".
 *
 * Covers the three shapes the API uses for absence, so individual fields don't
 * each have to remember:
 *   - `null` / `undefined` — genuinely unset
 *   - `''` — pydantic string fields default to empty rather than null
 *   - `'unknown'` — the sentinel `determinism`, `time_dynamics` and `spatial`
 *     carry when a model has not been characterized. Rendering it verbatim put
 *     the literal word "unknown" on screen as though it were a finding.
 */
function isAbsent(value: React.ReactNode): boolean {
  if (value === null || value === undefined || value === false) return true;
  if (typeof value !== 'string') return false;
  const normalized = value.trim().toLowerCase();
  return normalized === '' || normalized === 'unknown';
}

/**
 * States an absence as a fact instead of hiding it.
 *
 * The first pass deleted whole sections when their data was missing, which —
 * given that only ~12 of the model detail response's 45 fields are populated by
 * ingestion — made the page's structure vary per model and usually collapse to
 * almost nothing. Every registry this page competes with (Hugging Face,
 * BioModels, nf-core, Zenodo) does the opposite: keep the frame, name what is
 * missing. An em dash cannot do that, and gives assistive tech nothing.
 */
export function NotRecorded({
  children = 'Not recorded',
}: {
  children?: React.ReactNode;
}) {
  return <span className="text-default-800 italic">{children}</span>;
}
