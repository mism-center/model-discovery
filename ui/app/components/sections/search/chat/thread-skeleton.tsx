/**
 * Stand-in for a conversation named in the URL but not yet read back.
 *
 * Conversations live only in IndexedDB, which is async and client-only, so
 * there is always a frame or two on load where the route knows *which*
 * conversation to show but not its contents. Reserving the thread's shape
 * keeps that moment reading as loading rather than as an empty page.
 */
export function ThreadSkeleton() {
  return (
    <div aria-hidden="true" className="animate-pulse py-10">
      <div className="relative pl-6">
        <span className="absolute left-0 top-0 h-full w-px bg-default-200" />
        <span className="absolute left-0 top-0 h-8 w-0.5 bg-default-200" />

        <div className="h-6 w-3/5 rounded bg-default-200" />

        <div className="mt-6 max-w-[68ch] space-y-3">
          <div className="h-4 w-full rounded bg-default-100" />
          <div className="h-4 w-11/12 rounded bg-default-100" />
          <div className="h-4 w-4/5 rounded bg-default-100" />
        </div>

        <div className="mt-8 space-y-3">
          <div className="h-3 w-32 rounded bg-default-200" />
          <div className="h-20 w-full rounded-2xl bg-default-100" />
          <div className="h-20 w-full rounded-2xl bg-default-100" />
        </div>
      </div>
    </div>
  );
}
