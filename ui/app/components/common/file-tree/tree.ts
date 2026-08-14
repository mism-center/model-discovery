import type { ResourceFileItem } from '~/api';

/** A file leaf: the API item plus its basename. */
export interface FileTreeFile {
  kind: 'file';
  name: string;
  path: string;
  file: ResourceFileItem;
}

/** A directory node. `fileCount` and `sizeBytes` cover the whole subtree. */
export interface FileTreeDirectory {
  kind: 'dir';
  name: string;
  path: string;
  children: FileTreeNode[];
  fileCount: number;
  sizeBytes: number;
}

export type FileTreeNode = FileTreeDirectory | FileTreeFile;

interface Draft {
  directories: Map<string, Draft>;
  files: Array<{ name: string; file: ResourceFileItem }>;
}

/**
 * Turn the flat `GET /resources/{id}/files` listing into a hierarchy.
 *
 * The endpoint reports one entry per file with a slash-joined relative path and
 * no entries for the directories themselves, so every intermediate directory
 * here is inferred from the paths. An entry that *does* arrive with
 * `is_dir: true` creates a directory node and contributes no file.
 */
export function buildFileTree(files: ResourceFileItem[]): FileTreeNode[] {
  const root: Draft = { directories: new Map(), files: [] };

  for (const file of files) {
    const segments = file.path.split('/').filter(Boolean);
    if (segments.length === 0) continue;

    const directorySegments = file.is_dir ? segments : segments.slice(0, -1);
    let draft = root;
    for (const segment of directorySegments) {
      let child = draft.directories.get(segment);
      if (!child) {
        child = { directories: new Map(), files: [] };
        draft.directories.set(segment, child);
      }
      draft = child;
    }
    if (!file.is_dir) draft.files.push({ name: segments.at(-1)!, file });
  }

  return finalize(root, '');
}

/** Numeric collation so `run2` sorts before `run10`. */
function byName(a: { name: string }, b: { name: string }): number {
  return a.name.localeCompare(b.name, undefined, { numeric: true });
}

/** Resolve a draft into sorted nodes, directories first, rolling up totals. */
function finalize(draft: Draft, prefix: string): FileTreeNode[] {
  const directories: FileTreeDirectory[] = [...draft.directories.entries()].map(
    ([name, child]) => {
      const path = prefix === '' ? name : `${prefix}/${name}`;
      const children = finalize(child, path);
      return {
        kind: 'dir',
        name,
        path,
        children,
        fileCount: children.reduce(
          (total, node) => total + (node.kind === 'dir' ? node.fileCount : 1),
          0
        ),
        sizeBytes: children.reduce(
          (total, node) =>
            total +
            (node.kind === 'dir' ? node.sizeBytes : node.file.size_bytes),
          0
        ),
      };
    }
  );
  const files: FileTreeFile[] = draft.files.map(({ name, file }) => ({
    kind: 'file',
    name,
    path: file.path,
    file,
  }));

  directories.sort(byName);
  files.sort(byName);

  return [...directories, ...files];
}

/** Every directory path in the tree, for "expand all". */
export function directoryPaths(nodes: FileTreeNode[]): string[] {
  return nodes.flatMap((node) =>
    node.kind === 'dir' ? [node.path, ...directoryPaths(node.children)] : []
  );
}
