import { Skeleton } from '@heroui/react';

/**
 * First-paint placeholder for the model details page. Mirrors the two-column
 * layout (main content + sidebar) so hydration doesn't shift the layout.
 */
export function ModelDetailsSkeleton() {
  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-10"
      aria-busy="true"
    >
      <div className="flex flex-col gap-6">
        <Skeleton className="h-9 w-2/3 rounded-lg" />
        <Skeleton className="h-4 w-full rounded" />
        <Skeleton className="h-4 w-5/6 rounded" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-20 rounded" />
          <Skeleton className="h-5 w-24 rounded" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-40 w-full rounded-2xl" />
        ))}
      </div>
      <div className="hidden lg:flex flex-col gap-3">
        <Skeleton className="h-72 w-full rounded-2xl" />
      </div>
    </div>
  );
}
