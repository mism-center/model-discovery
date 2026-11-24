import cn from 'classnames';

/**
 * Inline "nothing here" state for a collection section body.
 *
 * Mirrors `ApiErrorDisplay`'s composition — centered icon, title, one line of
 * description, optional action — so an empty section and a failed section read
 * as the same family. Field sections use `SectionAbsence` instead; a centered
 * icon block per empty field section would decorate the emptiness rather than
 * get out of the way.
 *
 * `default-800` is the floor for text: the project's `default` ramp is a surface
 * scale where 500/600 measure 1.48:1 and 2.19:1 on white.
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
      {/* 700 (3.45:1) is the floor a 40px glyph needs to register; 600 is 2.19:1
          and effectively invisible. */}
      <Icon
        className="size-10 text-default-700"
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
