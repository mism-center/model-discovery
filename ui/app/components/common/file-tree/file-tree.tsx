import { useState } from 'react';
import cn from 'classnames';
import { useDisclosure } from '@heroui/react';
import {
  ArrowDownTrayIcon,
  ChevronRightIcon,
  CodeBracketIcon,
  DocumentIcon,
  DocumentTextIcon,
  EyeIcon,
  FolderIcon,
  FolderOpenIcon,
  PhotoIcon,
  TableCellsIcon,
} from '@heroicons/react/16/solid';
import pluralize from 'pluralize';

import type { ResourceFileItem } from '~/api';
import { resourceDownloadUrl } from '~/api';
import type { PreviewCategory } from '~/components/sections/search/search-results/file-preview-modal';
import {
  FilePreviewModal,
  previewCategory,
} from '~/components/sections/search/search-results/file-preview-modal';
import { formatBytes } from '~/utils/format';
import type { FileTreeDirectory, FileTreeFile, FileTreeNode } from './tree';

const CATEGORY_ICONS: Record<
  NonNullable<PreviewCategory>,
  React.ComponentType<React.SVGProps<SVGSVGElement>>
> = {
  image: PhotoIcon,
  table: TableCellsIcon,
  markdown: DocumentTextIcon,
  code: CodeBracketIcon,
  text: DocumentTextIcon,
};

/** `comfortable` for a page section, `compact` for a list inside a card. */
export type FileTreeDensity = 'comfortable' | 'compact';

interface Density {
  /** Gap between a row's leading icons and its name, shared by both. */
  gap: string;
  row: string;
  icon: string;
  chevron: string;
  name: string;
  meta: string;
  /** Gap between a row's trailing actions and figures. */
  actions: string;
  /**
   * Width reserved for one right-aligned figure. Fixed so the sizes down a tree
   * form a column and the action icons before them stay put; a `min-` bound
   * rather than a hard width, so an unusually long figure grows instead of
   * clipping.
   */
  figure: string;
  /** Indent and branch rule for one nesting level. */
  branch: string;
}

const DENSITIES: Record<FileTreeDensity, Density> = {
  comfortable: {
    gap: 'gap-2',
    row: 'py-1.5 px-1',
    icon: 'size-4',
    chevron: 'size-3.5',
    name: 'text-sm',
    meta: 'text-xs',
    actions: 'gap-3',
    figure: 'min-w-16',
    // ml puts the rule under the chevron's centre (row px + half the chevron),
    // so it reads as the branch its children hang off.
    branch: 'ml-[11px] pl-2.5',
  },
  compact: {
    gap: 'gap-2',
    row: 'py-1 px-1.5',
    icon: 'size-3.5',
    chevron: 'size-3',
    name: 'text-xs',
    meta: 'text-xs',
    actions: 'gap-2',
    figure: 'min-w-14',
    branch: 'ml-[12px] pl-2',
  },
};

const FOCUS_RING =
  'outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded';
const ROW = 'group flex items-center w-full rounded hover:bg-primary/4';
const NAME = 'flex items-center min-w-0 text-default-900';

/** Thumbnail box: big enough to read, and square so rows stay a grid. */
const THUMBNAIL = 'size-6';

export interface FileTreeProps {
  resourceId: string;
  /** Tree from `useFileTree`. */
  nodes: FileTreeNode[];
  expanded: Set<string>;
  onToggle: (path: string) => void;
  density?: FileTreeDensity;
  /** Render image files as their own thumbnail instead of a type icon. */
  thumbnails?: boolean;
}

/** Everything a row needs, threaded through the recursion unchanged. */
interface RowContext {
  resourceId: string;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  density: Density;
  thumbnails: boolean;
  /** Width of every row's leading graphic, so all names share one left edge. */
  slot: string;
  onPreview: (file: ResourceFileItem) => void;
}

/**
 * A row's leading graphic, in a box of one fixed width. Without it a thumbnail
 * would indent its filename past the icon rows beside it.
 */
function RowSlot({
  context,
  children,
}: {
  context: RowContext;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        context.slot,
        'flex shrink-0 items-center justify-center overflow-hidden'
      )}
    >
      {children}
    </span>
  );
}

/**
 * Nested disclosure list over a resource's files, with per-file preview and
 * download. Owns the preview modal; expansion state comes from `useFileTree`.
 *
 * Deliberately not the ARIA `tree` pattern: tree items own the arrow keys and
 * expect a single focus stop per row, which cannot hold rows that carry their
 * own preview and download controls. Nested lists of `aria-expanded` buttons
 * give the same structure with plain tab order and no key interception.
 */
export function FileTree({
  resourceId,
  nodes,
  expanded,
  onToggle,
  density = 'comfortable',
  thumbnails = false,
}: FileTreeProps) {
  const preview = useDisclosure();
  const [previewFile, setPreviewFile] = useState<ResourceFileItem | null>(null);

  const context: RowContext = {
    resourceId,
    expanded,
    onToggle,
    density: DENSITIES[density],
    thumbnails,
    slot: thumbnails ? THUMBNAIL : DENSITIES[density].icon,
    onPreview: (file) => {
      setPreviewFile(file);
      preview.onOpen();
    },
  };

  return (
    <>
      <TreeLevel nodes={nodes} context={context} />
      {preview.isOpen && previewFile && (
        <FilePreviewModal
          isOpen
          onClose={preview.onClose}
          resourceId={resourceId}
          file={previewFile}
        />
      )}
    </>
  );
}

function TreeLevel({
  nodes,
  context,
}: {
  nodes: FileTreeNode[];
  context: RowContext;
}) {
  return (
    <ul className="flex flex-col">
      {nodes.map((node) =>
        node.kind === 'dir' ? (
          <DirectoryRow key={node.path} node={node} context={context} />
        ) : (
          <FileRow key={node.path} node={node} context={context} />
        )
      )}
    </ul>
  );
}

/**
 * A row's trailing group: actions, then figures. Shared by both row kinds so a
 * directory's total lands in the same column as the file sizes below it.
 */
function RowTail({
  context,
  children,
}: {
  context: RowContext;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'ml-auto flex items-center shrink-0 pl-2',
        context.density.actions
      )}
    >
      {children}
    </div>
  );
}

/** One right-aligned figure in the trailing group: a size, or a file count. */
function Figure({
  context,
  children,
}: {
  context: RowContext;
  children: React.ReactNode;
}) {
  const { density } = context;
  return (
    <span
      className={cn(
        density.meta,
        density.figure,
        'text-right text-default-800 tabular-nums'
      )}
    >
      {children}
    </span>
  );
}

function DirectoryRow({
  node,
  context,
}: {
  node: FileTreeDirectory;
  context: RowContext;
}) {
  const { density } = context;
  const isOpen = context.expanded.has(node.path);

  return (
    <li>
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => context.onToggle(node.path)}
        title={node.path}
        className={cn(
          ROW,
          density.gap,
          density.row,
          'cursor-pointer text-default-900 hover:text-primary',
          FOCUS_RING
        )}
      >
        <ChevronRightIcon
          aria-hidden="true"
          className={cn(
            density.chevron,
            'shrink-0 text-default-700 transition-transform duration-150 group-hover:text-primary',
            isOpen && 'rotate-90'
          )}
        />
        <RowSlot context={context}>
          {isOpen ? (
            <FolderOpenIcon aria-hidden="true" className={density.icon} />
          ) : (
            <FolderIcon aria-hidden="true" className={density.icon} />
          )}
        </RowSlot>
        <span className={cn(density.name, 'truncate font-semibold')}>
          {node.name}
        </span>
        {/* The count takes the slot a file row spends on its actions, so the
            size stays in the same column for both row kinds. */}
        <RowTail context={context}>
          <Figure context={context}>
            {pluralize('file', node.fileCount, true)}
          </Figure>
          <Figure context={context}>{formatBytes(node.sizeBytes)}</Figure>
        </RowTail>
      </button>
      {isOpen && (
        <div className={cn(density.branch, 'border-l border-default-200')}>
          <TreeLevel nodes={node.children} context={context} />
        </div>
      )}
    </li>
  );
}

function FileRow({
  node,
  context,
}: {
  node: FileTreeFile;
  context: RowContext;
}) {
  const { density, resourceId } = context;
  const category = previewCategory(node.path);
  const action = cn(
    'text-default-800 group-hover:text-primary shrink-0',
    FOCUS_RING
  );

  const label = (
    <>
      <RowSlot context={context}>
        {context.thumbnails && category === 'image' ? (
          <img
            src={resourceDownloadUrl(resourceId, node.path, { inline: true })}
            alt=""
            loading="lazy"
            className="size-full rounded object-cover bg-default-100"
          />
        ) : (
          <FileTypeIcon category={category} className={density.icon} />
        )}
      </RowSlot>
      <span className={cn(density.name, 'truncate')}>{node.name}</span>
    </>
  );

  return (
    <li>
      {/*
       * A div, not one big anchor: a button cannot nest inside an anchor, and
       * previewable rows need both affordances — the row itself previews, and
       * the eye icon makes that discoverable.
       *
       * The row button takes no aria-label, so its visible filename names it: an
       * explicit one would announce the same string as the eye icon beside it,
       * twice per row.
       */}
      <div className={cn(ROW, density.gap, density.row)}>
        {/* Aligns file names with the folder names above them, whose chevron
            occupies this width. */}
        <span aria-hidden="true" className={cn(density.chevron, 'shrink-0')} />
        {category ? (
          <button
            type="button"
            onClick={() => context.onPreview(node.file)}
            title={node.path}
            className={cn(
              NAME,
              density.gap,
              'group-hover:text-primary cursor-pointer',
              FOCUS_RING
            )}
          >
            {label}
          </button>
        ) : (
          <span className={cn(NAME, density.gap)} title={node.path}>
            {label}
          </span>
        )}
        <RowTail context={context}>
          {category ? (
            <button
              type="button"
              onClick={() => context.onPreview(node.file)}
              aria-label={`Preview ${node.path}`}
              className={cn(action, 'cursor-pointer')}
            >
              <EyeIcon aria-hidden="true" className={density.icon} />
            </button>
          ) : (
            // Holds the column open so the download icons stay aligned past a
            // file that cannot be previewed.
            <span aria-hidden="true" className={cn(density.icon, 'shrink-0')} />
          )}
          <a
            href={resourceDownloadUrl(resourceId, node.path)}
            download
            aria-label={`Download ${node.path}`}
            className={action}
          >
            <ArrowDownTrayIcon aria-hidden="true" className={density.icon} />
          </a>
          <Figure context={context}>{formatBytes(node.file.size_bytes)}</Figure>
        </RowTail>
      </div>
    </li>
  );
}

/**
 * Row icon, keyed off the same classification that decides previewability, so
 * there is no second extension table to keep in step. A `null` category (a
 * binary) falls through to the generic document icon.
 */
function FileTypeIcon({
  category,
  className,
}: {
  category: PreviewCategory;
  className: string;
}) {
  const Icon = category ? CATEGORY_ICONS[category] : DocumentIcon;
  return <Icon aria-hidden="true" className={cn(className, 'shrink-0')} />;
}
