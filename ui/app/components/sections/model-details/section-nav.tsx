import { useEffect, useState } from 'react';
import cn from 'classnames';

import { FIELD_LABEL } from '~/components/common/definition-field';

export type SectionLink = { id: string; label: string };

/**
 * Sticky table of contents for the detail page, living in the shell's left rail
 * (the slot search and runs give their filter sidebars).
 *
 * `top-16` clears the site header — a HeroUI `Navbar` with a 4rem
 * `--navbar-height` that `header.tsx` pins `sticky`. Anything smaller puts the
 * first link under an opaque navy bar once the page scrolls.
 *
 * Anchors are real links, so every section is deep-linkable and the nav works
 * before hydration.
 */
export function SectionNav({ sections }: { sections: SectionLink[] }) {
  const active = useActiveSection(sections);

  return (
    <div className="hidden lg:block sticky top-16 self-start p-6">
      <nav aria-label="On this page">
        <p className={cn(FIELD_LABEL, 'mb-3')}>On this page</p>
        <ul className="flex flex-col gap-0.5">
          {sections.map(({ id, label }) => (
            <li key={id}>
              <a
                href={`#${id}`}
                aria-current={active === id ? 'location' : undefined}
                className={cn(
                  'block rounded-md px-3 py-1.5 text-sm transition-colors',
                  'outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                  active === id
                    ? 'bg-primary/8 font-semibold text-primary'
                    : 'text-default-900 hover:bg-primary/4 hover:text-primary'
                )}
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

/**
 * Track which section is in view, using a top-biased root margin so a section
 * activates once its heading reaches the area below the navbar rather than when
 * it happens to be centered. No highlight when IntersectionObserver is missing.
 */
function useActiveSection(sections: SectionLink[]): string | undefined {
  const [active, setActive] = useState<string>();
  const ids = sections.map((s) => s.id).join(',');

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;

    const elements = ids
      .split(',')
      .map((id) => document.querySelector(`#${id}`))
      .filter((el): el is HTMLElement => el !== null);
    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Highest intersecting section wins. A manual scan rather than a sort,
        // so this needs neither `toSorted` (absent from this tsconfig's lib) nor
        // an eslint escape hatch for mutating `sort`.
        let topMost: IntersectionObserverEntry | undefined;
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          if (
            !topMost ||
            entry.boundingClientRect.top < topMost.boundingClientRect.top
          ) {
            topMost = entry;
          }
        }
        if (topMost) setActive(topMost.target.id);
      },
      // -80px matches `scroll-mt-20` on SectionCard, so the highlight changes at
      // exactly the offset an anchored section lands at.
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 }
    );

    for (const el of elements) observer.observe(el);
    return () => observer.disconnect();
  }, [ids]);

  return active;
}
