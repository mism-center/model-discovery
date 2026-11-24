import { Skeleton } from '@heroui/react';

/**
 * First-paint placeholder for the model details page.
 *
 * Renders inside the same content pane as the real body, so it only mirrors the
 * body's vertical rhythm (`flex flex-col gap-8`) rather than re-pasting the page
 * grid.
 *
 * Shapes track the real section list: four field grids (characterization,
 * biology, execution, provenance) and three list-shaped sections (inputs &
 * outputs, files, run history). Getting the count and shape right is what keeps
 * hydration from shifting the page.
 */
export function ModelDetailsSkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-busy="true">
      {/* Header: breadcrumbs, title, byline, description, tag row. */}
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-64 rounded" />
        <Skeleton className="h-9 w-2/3 rounded-lg" />
        <Skeleton className="h-4 w-80 max-w-full rounded" />
        <Skeleton className="h-4 w-full max-w-3xl rounded" />
        <Skeleton className="h-4 w-5/6 max-w-3xl rounded" />
        <div className="flex gap-1.5 pt-1">
          <Skeleton className="h-5 w-20 rounded-sm" />
          <Skeleton className="h-5 w-24 rounded-sm" />
        </div>
      </div>

      <SectionSkeleton kind="grid" />
      <SectionSkeleton kind="grid" />
      <SectionSkeleton kind="list" />
      <SectionSkeleton kind="grid" />
      <SectionSkeleton kind="list" />
      <SectionSkeleton kind="list" />
      <SectionSkeleton kind="grid" />
    </div>
  );
}

/**
 * Placeholder for a section body that loads on its own query (Files, Run
 * history). Those sections resolve after the model does, so a spinner-and-text
 * row would appear *inside* an otherwise finished page; a skeleton of the right
 * shape reads as the same loading pass.
 */
export function SectionListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full rounded" />
      ))}
    </div>
  );
}

/**
 * Placeholder for the nav rail, so the 280px gutter reads as loading rather than
 * as an empty column.
 */
export function SectionNavSkeleton({ items = 7 }: { items?: number }) {
  return (
    <div className="sticky top-16 self-start p-6" aria-busy="true">
      <Skeleton className="h-3 w-24 rounded mb-4" />
      <div className="flex flex-col gap-2">
        {Array.from({ length: items }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-40 rounded" />
        ))}
      </div>
    </div>
  );
}

function SectionSkeleton({ kind }: { kind: 'grid' | 'list' }) {
  return (
    <div className="flex flex-col gap-4 border-t border-default-200 pt-8">
      <Skeleton className="h-6 w-48 rounded" />
      {kind === 'grid' ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-2">
              <Skeleton className="h-3 w-24 rounded" />
              <Skeleton className="h-4 w-32 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full rounded" />
          ))}
        </div>
      )}
    </div>
  );
}
