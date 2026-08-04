import cn from 'classnames';

import { NotRecorded } from '~/components/common/definition-field';

export { FIELD_LABEL } from '~/components/common/definition-field';

/** Stable anchor id for a section, so `/models/:id#execution` deep-links. */
export function sectionId(title: string): string {
  return title
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, '-')
    .replaceAll(/^-|-$/g, '');
}

/**
 * One titled region of the detail page.
 *
 * Deliberately flat — a rule and a heading, not a bordered elevated card. None
 * of the registries this page competes with (Hugging Face, BioModels, nf-core,
 * Zenodo, Bioconductor) wraps each metadata group in its own card; they use one
 * continuous surface with lightweight group headings. Stacking six rounded
 * cards on a gray page made every group look equally important and left the
 * metadata rail — which used the *same* background as the page — looking like
 * unstyled floating text.
 *
 * Sections always render, including when they have no data. The first pass
 * returned `null` from each section when its fields were empty, which meant the
 * page's structure changed per model and, since only ~12 of the 45 response
 * fields are populated by ingestion, usually collapsed to a title and a file
 * list. Naming an absence is information; silently removing the section is not.
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
  return (
    <section
      id={sectionId(title)}
      // scroll-mt clears the 64px sticky navbar when an anchor is targeted.
      className={cn(
        'scroll-mt-20 border-t border-default-200 pt-8 first:border-t-0 first:pt-0',
        className
      )}
    >
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <h2 className="text-lg font-headline font-bold text-primary">
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-sm text-default-800">{description}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/**
 * A sub-heading inside a section.
 *
 * Previously every section hand-rolled `<h3 class="text-xs … text-default-800">`,
 * an `<h3>` rendered *smaller and fainter* than the body text beneath it — an
 * inverted hierarchy repeated in six places.
 */
export function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-default-900 mb-2">{children}</h3>
  );
}

export {
  DefinitionField as Field,
  NotRecorded,
} from '~/components/common/definition-field';

type ChipTone = 'primary' | 'neutral' | 'secondary';

/**
 * Chip backgrounds are all light, with dark foregrounds, so every tone clears
 * WCAG AA. The previous `secondary` tone put `text-secondary` on
 * `bg-secondary-100` at 10px bold — 3.09:1.
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
