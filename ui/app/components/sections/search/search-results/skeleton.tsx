import { Skeleton } from '@heroui/react';

export function ResultSkeleton() {
  return (
    <div className="bg-transparent p-6 rounded-2xl flex items-stretch justify-between gap-6 border border-transparent">
      {/* Left content */}
      <div className="flex-1 min-w-0">
        {/* Badges + header detail */}
        <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
          <div className="flex flex-wrap items-center gap-2">
            <Skeleton className="h-5 w-24 rounded-sm" />
          </div>
          <Skeleton className="h-4 w-36 rounded" />
        </div>

        {/* Title */}
        <Skeleton className="h-6 w-72 max-w-full rounded-md" />

        {/* Description */}
        <Skeleton className="h-4 w-full max-w-lg rounded-md mt-2" />

        {/* Scale badges */}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <Skeleton className="h-5 w-18 rounded-full" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-12 rounded-full" />
        </div>

        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-4 mt-3 min-h-8">
          <Skeleton className="h-4 w-24 rounded" />
          <Skeleton className="h-4 w-20 rounded" />
          <Skeleton className="h-4 w-20 rounded" />
        </div>
      </div>

      {/* Right side actions (bookmark top, view details bottom) */}
      <div className="flex flex-col justify-between items-end">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <Skeleton className="h-9 w-28 rounded-lg" />
      </div>
    </div>
  );
}
