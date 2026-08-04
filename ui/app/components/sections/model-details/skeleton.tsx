import { Skeleton } from '@heroui/react';

/**
 * First-paint placeholder for the model details page.
 *
 * Renders inside the same content pane as the real body, so it only has to
 * mirror the body's vertical rhythm (`flex flex-col gap-8`) rather than
 * re-pasting the page grid. The previous version duplicated the two-column
 * template by hand with `gap-10` where the real layout used `gap-8`, and put the
 * title inside the narrow column while the real header spanned full width — so
 * on hydration the heading jumped several hundred pixels sideways.
 */
export function ModelDetailsSkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-busy="true">
      {/* Header: breadcrumbs, title, description, tag row. */}
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-64 rounded" />
        <Skeleton className="h-9 w-2/3 rounded-lg" />
        <Skeleton className="h-4 w-full max-w-3xl rounded" />
        <Skeleton className="h-4 w-5/6 max-w-3xl rounded" />
        <div className="flex gap-1.5 pt-1">
          <Skeleton className="h-5 w-20 rounded-sm" />
          <Skeleton className="h-5 w-24 rounded-sm" />
        </div>
      </div>

      {/* One block per section, matching the fixed section list. */}
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="flex flex-col gap-4 border-t border-default-200 pt-8"
        >
          <Skeleton className="h-6 w-48 rounded" />
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((__, j) => (
              <div key={j} className="flex flex-col gap-2">
                <Skeleton className="h-3 w-24 rounded" />
                <Skeleton className="h-4 w-32 rounded" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
