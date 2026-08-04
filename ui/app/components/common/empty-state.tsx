import cn from 'classnames';

/**
 * Inline "nothing here" state for a section body.
 *
 * Deliberately mirrors `ApiErrorDisplay`'s composition — centered icon, title,
 * one line of description, optional action — so an empty section and a failed
 * section read as the same family instead of one being a designed state and the
 * other a stray gray sentence. The model detail page previously used bare
 * one-liners ("No files are stored with this model.", "This model hasn't been
 * run yet.") while every other surface in the app used the fuller pattern.
 *
 * `default-800` is the floor for text here: the project's `default` ramp is a
 * surface scale where 500/600 measure 1.48:1 and 2.19:1 on white.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center text-center gap-3 py-10',
        className
      )}
    >
      <Icon
        className="size-10 text-default-600"
        aria-hidden="true"
        strokeWidth={1.25}
      />
      <div className="flex flex-col gap-1 max-w-sm">
        <h3 className="text-base font-semibold text-default-900">{title}</h3>
        {description && (
          <p className="text-sm text-default-800 leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
