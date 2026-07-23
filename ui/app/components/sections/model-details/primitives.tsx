import cn from 'classnames';

/** A titled content card used for each stacked detail section. */
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
      className={cn(
        'rounded-2xl border border-default-200 bg-white p-6',
        className
      )}
    >
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <h2 className="text-lg font-headline font-bold text-primary">
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-sm text-default-600">{description}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Uppercase field label, matching the runs panel style. */
export const FIELD_LABEL =
  'text-[11px] font-bold uppercase tracking-wider text-default-600';

/** A label / value pair in a definition list. */
export function Field({
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
      <dd className="mt-1 text-[13px] text-default-900 break-words">
        {children}
      </dd>
    </div>
  );
}

type ChipTone = 'primary' | 'neutral' | 'secondary';

const CHIP_TONES: Record<ChipTone, string> = {
  primary: 'bg-primary-100 text-primary/80',
  neutral: 'bg-default-200 text-default-900/90',
  secondary: 'bg-secondary-100 text-secondary',
};

/** Small uppercase tag chip, matching the search-result card styling. */
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
        'px-2 py-0.5 rounded-xs text-[10px] font-bold uppercase tracking-tighter',
        CHIP_TONES[tone]
      )}
    >
      {children}
    </span>
  );
}

/** Render a list of string values as chips, or an em dash when empty. */
export function ChipList({
  values,
  tone = 'primary',
}: {
  values: string[] | null | undefined;
  tone?: ChipTone;
}) {
  if (!values || values.length === 0) {
    return <span className="text-default-500">—</span>;
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
