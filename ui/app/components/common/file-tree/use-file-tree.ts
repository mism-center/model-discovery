import { useMemo, useState } from 'react';

import type { ResourceFileItem } from '~/api';
import { buildFileTree, directoryPaths, type FileTreeNode } from './tree';

/** Stable identity so an absent listing doesn't rebuild the tree every render. */
const NO_FILES: ResourceFileItem[] = [];

/** Whether a freshly loaded tree starts open or closed. */
export type InitialExpansion = 'all' | 'none';

export interface FileTreeState {
  nodes: FileTreeNode[];
  expanded: Set<string>;
  toggle: (path: string) => void;
  /** Open or close every directory at once. */
  setAllExpanded: (open: boolean) => void;
  allExpanded: boolean;
  hasDirectories: boolean;
}

/**
 * Tree structure and expansion state for a resource's file listing.
 *
 * Split from `FileTree` so a caller can drive expansion from chrome of its own —
 * the model detail page puts "Expand all" in the section header, beside the
 * download link — without either of them owning a second copy of the state.
 */
export function useFileTree(
  files: ResourceFileItem[] | undefined,
  { initialExpansion = 'none' }: { initialExpansion?: InitialExpansion } = {}
): FileTreeState {
  /**
   * `null` until the reader touches a folder, so `initialExpansion` applies to
   * the tree the query eventually delivers rather than the empty one present on
   * first render.
   */
  const [expanded, setExpanded] = useState<Set<string> | null>(null);

  const nodes = useMemo(() => buildFileTree(files ?? NO_FILES), [files]);
  const allDirectories = useMemo(() => directoryPaths(nodes), [nodes]);
  const effective = useMemo(
    () =>
      expanded ??
      new Set(initialExpansion === 'all' ? allDirectories : undefined),
    [expanded, allDirectories, initialExpansion]
  );

  return {
    nodes,
    expanded: effective,
    toggle: (path: string) => {
      const next = new Set(effective);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      setExpanded(next);
    },
    setAllExpanded: (open: boolean) =>
      setExpanded(open ? new Set(allDirectories) : new Set()),
    allExpanded:
      allDirectories.length > 0 &&
      allDirectories.every((path) => effective.has(path)),
    hasDirectories: allDirectories.length > 0,
  };
}
