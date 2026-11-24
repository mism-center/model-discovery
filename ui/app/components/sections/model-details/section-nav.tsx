import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import cn from 'classnames';

import { FIELD_LABEL } from '~/components/common/definition-field';
import { useSectionCollapse } from './section-collapse';

export type SectionLink = {
  id: string;
  label: string;
  /** Anchored subheadings within the section, in document order. */
  children?: { id: string; label: string }[];
};

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
  const collapse = useSectionCollapse();

  /**
   * Expand the target before the anchor's own navigation scrolls to it — with
   * enough sections closed the document is too short to bring a late one to the
   * top, and the browser clamps the scroll. `flushSync` commits the expansion
   * during dispatch, which runs before the default action.
   *
   * No `preventDefault`: driving the jump with `location.hash` instead reads as a
   * location change, and React Router's scroll restoration overrides it.
   *
   * `sectionId` is the section to open, which for a subsection link is its
   * parent — a subheading anchor is inside the panel that has to open first.
   */
  function jumpTo(sectionIdToOpen: string) {
    if (!collapse) return;
    flushSync(() => collapse.expand(sectionIdToOpen));
  }

  return (
    <div className="hidden lg:block sticky top-16 self-start p-6">
      <nav aria-label="On this page">
        <p className={cn(FIELD_LABEL, 'mb-3')}>On this page</p>
        <ul className="flex flex-col gap-0.5">
          {sections.map((section) => {
            const childActive = section.children?.some(
              (child) => child.id === active
            );
            return (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  onClick={() => jumpTo(section.id)}
                  aria-current={active === section.id ? 'location' : undefined}
                  className={cn(
                    'block rounded-md px-3 py-1.5 text-sm transition-colors',
                    'outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                    active === section.id
                      ? 'bg-primary/8 font-semibold text-primary'
                      : cn(
                          'hover:bg-primary/4 hover:text-primary',
                          // A section whose subsection is active stays emphasised,
                          // so the rail always shows where you are at both levels.
                          childActive
                            ? 'font-semibold text-primary'
                            : 'text-default-900'
                        )
                  )}
                >
                  {section.label}
                </a>
                {section.children && section.children.length > 0 && (
                  <ul className="my-0.5 ml-4 flex flex-col gap-0.5 border-l border-default-200 pl-2">
                    {section.children.map((child) => (
                      <li key={child.id}>
                        <a
                          href={`#${child.id}`}
                          onClick={() => jumpTo(section.id)}
                          aria-current={
                            active === child.id ? 'location' : undefined
                          }
                          className={cn(
                            'block rounded-md px-2 py-1 text-xs transition-colors',
                            'outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                            active === child.id
                              ? 'bg-primary/8 font-semibold text-primary'
                              : 'text-default-800 hover:bg-primary/4 hover:text-primary'
                          )}
                        >
                          {child.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}

/**
 * 80px matches `scroll-mt-20`, the offset an anchored heading lands at. The extra
 * pixel keeps a heading scrolled exactly to its anchor counted as reached.
 */
const ACTIVE_OFFSET = 81;

/**
 * Track which section or subsection is in view: the last anchor whose top has
 * passed under the navbar.
 *
 * Not an IntersectionObserver picking the topmost intersecting element, which is
 * what this was before subsections existed. That cannot express nesting — a
 * `<section>` box spans all of its own subheadings, so while you are anywhere
 * inside it, it intersects with the most negative top and always outranks them.
 * Subsections would never light up. "Last one passed" ranks by document order
 * instead, and since a subheading comes after the section it belongs to, the
 * deepest heading you have scrolled past naturally wins.
 */
function useActiveSection(sections: SectionLink[]): string | undefined {
  const [active, setActive] = useState<string>();
  const collapse = useSectionCollapse();

  // Subheadings unmount when their section collapses, so this has to re-measure
  // on collapse as well as when the section list changes.
  const ids = sections
    .flatMap((section) => [
      section.id,
      ...(section.children ?? []).map((child) => child.id),
    ])
    .join(',');
  const expandedSignature = sections
    .map((section) => (collapse?.isExpanded(section.id) ? '1' : '0'))
    .join('');

  useEffect(() => {
    const idList = ids.split(',');
    let frame = 0;

    function measure() {
      frame = 0;
      let passed: string | undefined;
      let first: string | undefined;
      for (const id of idList) {
        const el = document.querySelector(`#${id}`);
        if (!el) continue;
        first ??= id;
        if (el.getBoundingClientRect().top <= ACTIVE_OFFSET) passed = id;
      }
      // At the top of the page nothing has passed yet, so hold the first anchor
      // rather than leaving the rail with no current item.
      setActive(passed ?? first);
    }

    function schedule() {
      frame ||= requestAnimationFrame(measure);
    }

    measure();
    globalThis.addEventListener('scroll', schedule, { passive: true });
    globalThis.addEventListener('resize', schedule);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      globalThis.removeEventListener('scroll', schedule);
      globalThis.removeEventListener('resize', schedule);
    };
  }, [ids, expandedSignature]);

  return active;
}
