import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigation } from 'react-router';

/**
 * How long a navigation must be in flight before the bar appears.
 *
 * Low, because the bar's whole job is to answer "did my click register?" and a
 * hesitation is felt well before 200ms. Not zero, so a navigation that resolves
 * in a couple of frames stays silent instead of strobing the top of the viewport.
 */
const APPEAR_AFTER_MS = 80;

/**
 * Once shown, the bar stays for at least this long.
 *
 * Without it the fast-but-not-instant case is the worst of both: a bar that
 * appears for 20ms reads as a rendering glitch. With it, showing the bar is a
 * commitment — every appearance lasts long enough to register as progress.
 */
const MIN_VISIBLE_MS = 320;

/**
 * Top-of-viewport progress bar for router navigations.
 *
 * React Router blocks a transition until the target route's loader resolves, so
 * between the click and the new page there is a window where the *old* page is
 * still fully rendered and looks idle. Without this the app gives no signal at
 * all during that window.
 *
 * Sits directly under the site header — `top-16` matches the navbar's 4rem
 * `--navbar-height`, the same offset `section-nav.tsx` pins itself to — so it
 * reads as the page loading beneath the chrome rather than as part of it.
 *
 * 3px in the accent teal.
 *
 * Indeterminate on purpose: a loader's duration isn't knowable up front, so the
 * fill decelerates toward an asymptote instead of promising a finish line. It
 * reports "working", not "this far along", and simply stops when the navigation
 * ends.
 *
 * Scoped to pathname changes. Search filtering navigates too (it writes filter
 * state to the query string via `setSearchParams`), but that already swaps in
 * `ResultSkeleton` where the results are, so a second indicator up here would be
 * noise on the app's most-used interaction.
 */
export function NavigationProgress() {
  const navigation = useNavigation();
  const location = useLocation();
  const [visible, setVisible] = useState(false);
  const shownAt = useRef(0);

  const changingRoute =
    navigation.state !== 'idle' &&
    navigation.location !== undefined &&
    navigation.location.pathname !== location.pathname;

  useEffect(() => {
    if (changingRoute) {
      const timer = setTimeout(() => {
        shownAt.current = performance.now();
        setVisible(true);
      }, APPEAR_AFTER_MS);
      return () => clearTimeout(timer);
    }

    // Arrived. Hold the bar if it has not been up long enough to be legible;
    // `held` is negative-proof because `shownAt` is only ever set on show.
    const held = performance.now() - shownAt.current;
    if (!visible || held >= MIN_VISIBLE_MS) {
      setVisible(false);
      return;
    }
    const timer = setTimeout(() => setVisible(false), MIN_VISIBLE_MS - held);
    return () => clearTimeout(timer);
    // Keyed on `changingRoute` alone. `visible` is read but not tracked: this
    // effect only ever needs to run when a navigation starts or ends, and adding
    // it would re-run the teardown branch the moment the bar appears.
  }, [changingRoute]);

  if (!visible) return null;

  return (
    // `aria-hidden`: a visual echo of a navigation the user just initiated, and
    // the new page's title is announced on arrival regardless.
    // `z-30` keeps it under the navbar's `z-40`: the two never overlap, and the
    // bar should lose to any chrome that grows downward into it.
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 top-16 z-30 h-[3px] overflow-hidden"
    >
      {/* `motion-reduce` holds a static full-width bar: the signal survives, the
          movement doesn't. */}
      <div className="animate-nav-progress h-full w-full bg-success motion-reduce:animate-none" />
    </div>
  );
}
