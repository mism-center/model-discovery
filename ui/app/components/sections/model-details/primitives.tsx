import cn from 'classnames';
import { ChevronDownIcon } from '@heroicons/react/24/outline';

import { NotRecorded } from '~/components/common/definition-field';
import { useSectionCollapse } from './section-collapse';

export { FIELD_LABEL } from '~/components/common/definition-field';

/**
 * The app's link treatment. `text-primary` measures 14.8:1 on white; the
 * `text-secondary` this replaced was 4.5:1 and disagreed with every other anchor
 * in the app.
 */
export const LINK = 'text-primary hover:underline';

/** Stable anchor id for a section, so `/models/:id#execution` deep-links. */
export function sectionId(title: string): string {
  return title
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, '-')
    .replaceAll(/^-|-$/g, '');
}

/** Nav label for the page header, which anchors itself rather than via SectionCard. */
export const OVERVIEW_TITLE = 'Overview';

const SECTION_HEADING = 'text-lg font-headline font-bold text-primary';

/**
 * One titled region of the detail page: a rule and a heading, not an elevated
 * card. Stacking cards makes every metadata group look equally important; a
 * single continuous surface with lightweight headings does not.
 *
 * Sections always render, including when they have no data — only ~12 of the 45
 * response fields are populated by ingestion, so hiding empty ones would make
 * the page's structure (and its nav) change shape per model. A section with
 * nothing to show says so via `SectionAbsence` or `EmptyState`.
 *
 * Every section carries a top rule, including the first — which separates it
 * from the page header above.
 *
 * Collapsible under a `SectionCollapseProvider`, plain headings without one.
 */
export function SectionCard({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const collapse = useSectionCollapse();
  const id = sectionId(title);
  const expanded = collapse ? collapse.isExpanded(id) : true;
  const panelId = `${id}-panel`;

  return (
    <section
      id={id}
      // scroll-mt clears the 64px sticky navbar when an anchor is targeted.
      className={cn('scroll-mt-20 border-t border-default-200 pt-8', className)}
    >
      {/* `group` is on the row, not the button, so hovering the description
          lights the chevron too. */}
      <div
        className={cn(
          'group relative flex items-start justify-between gap-4',
          expanded ? 'mb-4' : 'mb-0'
        )}
      >
        <div className="min-w-0 flex-1">
          <h2 className={SECTION_HEADING}>
            {collapse ? (
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => collapse.toggle(id)}
                className={cn(
                  'flex w-full cursor-pointer items-center gap-2 text-left',
                  'outline-none',
                  // Stretched over the row so the description toggles too. The
                  // description stays a sibling: nesting it would fold the blurb
                  // into the button's accessible name and the h2's heading text.
                  'after:absolute after:inset-0 after:rounded-md',
                  'focus-visible:after:ring-2 focus-visible:after:ring-primary/50'
                )}
              >
                <span>{title}</span>
                <ChevronDownIcon
                  aria-hidden="true"
                  className={cn(
                    'ml-auto size-4 shrink-0 transition-transform duration-200',
                    'text-default-700 group-hover:text-primary',
                    !expanded && '-rotate-90'
                  )}
                />
              </button>
            ) : (
              title
            )}
          </h2>
          {description && (
            <p className="mt-1 text-sm text-default-800">{description}</p>
          )}
        </div>
        {/* `relative` lifts the action above the stretched hit area, so it stays
            its own control instead of toggling the section. */}
        {action && <div className="relative shrink-0">{action}</div>}
      </div>
      {/* The panel stays mounted so `aria-controls` resolves; only its contents
          unmount, which keeps collapsed content out of the tab order. */}
      <div id={panelId} hidden={!expanded}>
        {expanded && children}
      </div>
    </section>
  );
}

/**
 * Body for a field section that has no data at all.
 *
 * One statement replaces a grid of per-field "Not recorded" cells: naming one
 * absence is information, naming six in a row is a wall to scroll past. Field
 * sections use this; collection sections (Files, Run history) use the centered
 * `EmptyState`, because their emptiness is actionable and they only ever render
 * one such state at a time.
 */
export function SectionAbsence({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-sm">
      <NotRecorded>{children}</NotRecorded>
    </p>
  );
}

/**
 * Absence inside a dense table cell.
 *
 * "Not recorded" repeated across every cell of a four-column table is noise, so
 * this shows the conventional dash instead — but a bare em dash gives assistive
 * tech nothing, so the words go in an `sr-only` span beside it.
 */
export function AbsentCell() {
  return (
    <>
      <span aria-hidden="true" className="text-default-800">
        —
      </span>
      <span className="sr-only">Not recorded</span>
    </>
  );
}

/** A navigable subsection of a section: one `SubHeading` with an anchor. */
export type Subsection = { id: string; label: string };

/**
 * A sub-heading inside a section. `text-sm` semibold so it outranks the body
 * text beneath it. Pass `id` to make it a nav anchor.
 */
export function SubHeading({
  id,
  children,
}: {
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <h3
      id={id}
      className={cn(
        'text-sm font-semibold text-default-900 mb-2',
        id && 'scroll-mt-20'
      )}
    >
      {children}
    </h3>
  );
}

/**
 * Uppercase the first letter only.
 *
 * The characterization vocabularies are lowercase and hyphenated
 * (`deterministic`, `event-driven`, `non-spatial`) while `spatial` also admits
 * `1D`…`3D`. CSS `capitalize` breaks on both counts — it would yield
 * "Non-Spatial" and leave the rest of the string alone.
 */
export function sentenceCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export {
  DefinitionField as Field,
  hasValue,
  hasItems,
} from '~/components/common/definition-field';

type ChipTone = 'primary' | 'neutral' | 'secondary';

/**
 * Chip backgrounds are all light with dark foregrounds, so every tone clears
 * WCAG AA — `text-secondary` on `bg-secondary-100` would be 3.09:1.
 */
const CHIP_TONES: Record<ChipTone, string> = {
  primary: 'bg-primary-100 text-primary',
  neutral: 'bg-default-100 text-default-900',
  secondary: 'bg-secondary-100 text-default-900',
};

/** Small tag chip. `text-xs` from the type scale, not an arbitrary 10px. */
export function Chip({
  children,
  tone = 'primary',
}: {
  children: React.ReactNode;
  tone?: ChipTone;
}) {
  return (
    <span
      className={cn(
        'px-2 py-0.5 rounded-sm text-xs font-semibold',
        CHIP_TONES[tone]
      )}
    >
      {children}
    </span>
  );
}

/** Render values as chips, or state the absence. */
export function ChipList({
  values,
  tone = 'primary',
}: {
  values: string[] | null | undefined;
  tone?: ChipTone;
}) {
  if (!values || values.length === 0) {
    return <NotRecorded />;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {values.map((v) => (
        <Chip key={v} tone={tone}>
          {v}
        </Chip>
      ))}
    </div>
  );
}
