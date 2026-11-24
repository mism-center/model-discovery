import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

type SectionCollapse = {
  isExpanded: (id: string) => boolean;
  toggle: (id: string) => void;
  expand: (id: string) => void;
};

/** Undefined outside a provider, which `SectionCard` reads as "not collapsible". */
const SectionCollapseContext = createContext<SectionCollapse | undefined>(
  undefined
);

export function useSectionCollapse(): SectionCollapse | undefined {
  return useContext(SectionCollapseContext);
}

/**
 * Collapse state for the detail page's sections, shared because the nav rail has
 * to re-open a collapsed section before jumping to it.
 *
 * Tracks the *collapsed* ids, so "all open" is the empty set and sections need no
 * registration step — including Run history, which mounts late.
 */
export function SectionCollapseProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(
    () => new Set()
  );

  const expand = useCallback((id: string) => {
    setCollapsed((previous) => {
      // Same set back when already open, so the hash listener below can call this
      // unconditionally without re-rendering the page.
      if (!previous.has(id)) return previous;
      const next = new Set(previous);
      next.delete(id);
      return next;
    });
  }, []);

  const toggle = useCallback((id: string) => {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }, []);

  // Covers every route to a section other than the nav's own links, which expand
  // their target themselves: back/forward, and pasted `/models/:id#execution`.
  useEffect(() => {
    function expandHashTarget() {
      const id = globalThis.location.hash.slice(1);
      if (!id) return;
      expand(id);
      // Subsection anchors live inside a section, so expand the enclosing one
      // too — otherwise `#experiment-protocol` lands on a collapsed parent.
      const section = document.querySelector(`#${id}`)?.closest('section[id]');
      if (section) expand(section.id);
    }
    expandHashTarget();
    globalThis.addEventListener('hashchange', expandHashTarget);
    return () => globalThis.removeEventListener('hashchange', expandHashTarget);
  }, [expand]);

  const value = useMemo<SectionCollapse>(
    () => ({ isExpanded: (id) => !collapsed.has(id), toggle, expand }),
    [collapsed, toggle, expand]
  );

  return (
    <SectionCollapseContext.Provider value={value}>
      {children}
    </SectionCollapseContext.Provider>
  );
}
