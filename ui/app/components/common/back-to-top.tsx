import { useEffect, useState } from 'react';
import { ArrowUpIcon } from '@heroicons/react/16/solid';
import cn from 'classnames';

/**
 * Honours `prefers-reduced-motion`: smooth scrolling is what that setting exists
 * to suppress, and a several-thousand-pixel animated jump is exactly the motion
 * it targets.
 */
function scrollToTop() {
  const reduced = globalThis.matchMedia?.(
    '(prefers-reduced-motion: reduce)'
  ).matches;
  globalThis.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
}

/**
 * Floating "back to top" control for long scrolling pages.
 *
 * Appears once the page has scrolled past `threshold`, so it costs nothing on
 * pages (or models) short enough not to need it.
 */
export function BackToTop({
  threshold = 600,
  className,
}: {
  threshold?: number;
  className?: string;
}) {
  const visible = useScrolledBeyond(threshold);

  return (
    <button
      type="button"
      onClick={scrollToTop}
      aria-label="Back to top"
      // Kept mounted and faded, rather than conditionally rendered, so it can
      // transition in. `pointer-events-none` while hidden stops it swallowing
      // clicks over the page's bottom-right corner, and `invisible` keeps it out
      // of the tab order.
      className={cn(
        'fixed bottom-6 right-6 z-30 flex items-center justify-center',
        'size-10 rounded-full bg-primary text-white shadow-lg',
        'transition-opacity hover:bg-primary-800',
        'outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2',
        visible ? 'opacity-100' : 'opacity-0 pointer-events-none invisible',
        className
      )}
    >
      <ArrowUpIcon aria-hidden="true" className="size-4" />
    </button>
  );
}

/** Whether the window has scrolled further than `threshold` pixels. */
function useScrolledBeyond(threshold: number): boolean {
  const [beyond, setBeyond] = useState(false);

  useEffect(() => {
    const update = () => setBeyond(globalThis.scrollY > threshold);
    update();
    globalThis.addEventListener('scroll', update, { passive: true });
    return () => globalThis.removeEventListener('scroll', update);
  }, [threshold]);

  return beyond;
}
