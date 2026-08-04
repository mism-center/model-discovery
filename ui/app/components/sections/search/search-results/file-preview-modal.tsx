import { lazy, Suspense, useMemo } from 'react';
import {
  Button,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Spinner,
} from '@heroui/react';
import { ArrowDownTrayIcon } from '@heroicons/react/16/solid';
import { useQuery } from '@tanstack/react-query';
import Papa from 'papaparse';

import {
  resourceDownloadUrl,
  TEXT_PREVIEW_MAX_BYTES,
  type ResourceFileItem,
} from '~/api';
import { resourceFileTextQueryOptions } from '~/api/query/resources';

// Heavy renderers are lazy-loaded so they (and Prism/its grammars) stay out of
// the route/SSR bundle; the modal body only mounts after a client click, so
// they never run on the server. Keep this a pure `import(...)` — a static
// import from file-preview-syntax here would defeat the code-split.
const ReactMarkdown = lazy(() => import('react-markdown'));
const CodePreview = lazy(() => import('./file-preview-syntax'));

/** Map a lowercase file extension to a registered Prism language. */
function prismLanguageForExtension(extension: string): string {
  switch (extension) {
    case 'json': {
      return 'json';
    }
    case 'yaml':
    case 'yml': {
      return 'yaml';
    }
    case 'xml': {
      return 'markup';
    }
    case 'toml': {
      return 'toml';
    }
    default: {
      return 'text';
    }
  }
}

export type PreviewCategory =
  | 'image'
  | 'table'
  | 'markdown'
  | 'code'
  | 'text'
  | null;

// Extension sets mirror the taxonomy in run-output-files.tsx's FILE_TYPE_ICONS.
// Note: xlsx/xls/parquet are intentionally excluded from `table` — they are not
// text-parseable, so they get no preview (icon + download only).
const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp']);
const TABLE_EXTS = new Set(['csv', 'tsv']);
const CODE_EXTS = new Set(['json', 'yaml', 'yml', 'xml', 'toml']);
const TEXT_EXTS = new Set(['txt', 'log']);

function extensionOf(path: string): string {
  return path.split('.').pop()?.toLowerCase() ?? '';
}

/** Classify a file for previewing; `null` means "not previewable". */
export function previewCategory(path: string): PreviewCategory {
  const ext = extensionOf(path);
  if (IMAGE_EXTS.has(ext)) return 'image';
  if (TABLE_EXTS.has(ext)) return 'table';
  if (ext === 'md') return 'markdown';
  if (CODE_EXTS.has(ext)) return 'code';
  if (TEXT_EXTS.has(ext)) return 'text';
  return null;
}

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
};

const MAX_TABLE_ROWS = 500;

/** Render CSV/TSV text as a scrollable HTML table (first row as header). */
function CsvTable({ content, tsv }: { content: string; tsv: boolean }) {
  const rows = useMemo(() => {
    const parsed = Papa.parse<string[]>(content, {
      delimiter: tsv ? '\t' : '',
      skipEmptyLines: true,
    });
    return parsed.data;
  }, [content, tsv]);

  if (rows.length === 0) {
    return <p className="text-xs text-default-600">This file is empty.</p>;
  }

  const [header, ...body] = rows;
  const shown = body.slice(0, MAX_TABLE_ROWS);
  const truncated = body.length - shown.length;

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-auto rounded-lg border border-default-200">
        <table className="min-w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-default-100">
            <tr>
              {header.map((cell, i) => (
                <th
                  key={i}
                  scope="col"
                  className="whitespace-nowrap border-b border-default-200 px-3 py-2 text-left font-semibold text-default-800"
                >
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, r) => (
              <tr key={r} className="odd:bg-default-50/50">
                {row.map((cell, c) => (
                  <td
                    key={c}
                    className="whitespace-nowrap border-b border-default-100 px-3 py-1.5 font-mono text-default-800"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {truncated > 0 && (
        <p className="text-[11px] text-default-600">
          Showing first {MAX_TABLE_ROWS} rows ({truncated} more not shown).
          Download the file to see everything.
        </p>
      )}
    </div>
  );
}

interface FilePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  resourceId: string;
  file: ResourceFileItem;
}

export function FilePreviewModal({
  isOpen,
  onClose,
  resourceId,
  file,
}: FilePreviewModalProps) {
  const category = previewCategory(file.path);
  const ext = extensionOf(file.path);
  const tooLarge = file.size_bytes > TEXT_PREVIEW_MAX_BYTES;

  // Images render straight from the inline URL (browser handles it, cookies
  // sent same-origin). Everything else fetches text — but only when open, of a
  // sensible size, and not an image.
  const { data, isLoading, isError } = useQuery({
    ...resourceFileTextQueryOptions(resourceId, file.path),
    enabled: isOpen && category !== 'image' && category !== null && !tooLarge,
  });

  const centeredMessage = (message: React.ReactNode) => (
    <div className="flex min-h-40 items-center justify-center text-sm text-default-600">
      {message}
    </div>
  );

  let body: React.ReactNode;
  if (category === 'image') {
    body = (
      <div className="flex justify-center">
        <img
          src={resourceDownloadUrl(resourceId, file.path, { inline: true })}
          alt={file.name}
          className="max-h-[70vh] w-auto rounded-lg object-contain"
        />
      </div>
    );
  } else if (tooLarge) {
    body = centeredMessage(
      <span>
        This file is {formatBytes(file.size_bytes)} — too large to preview.
        Download it instead.
      </span>
    );
  } else if (isLoading) {
    body = (
      <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-default-600">
        <Spinner size="sm" />
        <span>Loading preview…</span>
      </div>
    );
  } else if (isError || data === undefined) {
    body = centeredMessage(
      <span className="text-danger">Couldn&apos;t load this file.</span>
    );
  } else
    switch (category) {
      case 'table': {
        body = <CsvTable content={data} tsv={ext === 'tsv'} />;

        break;
      }
      case 'markdown': {
        body = (
          <Suspense fallback={<Spinner size="sm" />}>
            {/* No typography plugin in this app — apply minimal readable defaults
            via arbitrary variants so markdown renders legibly on its own. */}
            <div className="text-sm text-default-900 leading-relaxed [&_h1]:text-lg [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-base [&_h2]:font-bold [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1.5 [&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_a]:text-primary [&_a]:underline [&_code]:font-mono [&_code]:text-[0.85em] [&_code]:bg-default-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_pre]:bg-default-50 [&_pre]:border [&_pre]:border-default-200 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-auto [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_blockquote]:border-l-2 [&_blockquote]:border-default-300 [&_blockquote]:pl-3 [&_blockquote]:text-default-700 [&_table]:border-collapse [&_th]:border [&_th]:border-default-200 [&_th]:px-2 [&_th]:py-1 [&_td]:border [&_td]:border-default-200 [&_td]:px-2 [&_td]:py-1">
              <ReactMarkdown>{data}</ReactMarkdown>
            </div>
          </Suspense>
        );

        break;
      }
      case 'code': {
        body = (
          <Suspense fallback={<Spinner size="sm" />}>
            <div className="overflow-auto rounded-lg border border-default-200 bg-default-50 p-3">
              <CodePreview language={prismLanguageForExtension(ext)}>
                {data}
              </CodePreview>
            </div>
          </Suspense>
        );

        break;
      }
      default: {
        // Plain text (txt/log) and any other fetched content.
        body = (
          <pre className="max-w-full overflow-auto rounded-lg border border-default-200 bg-default-50 p-3 text-xs whitespace-pre-wrap wrap-break-word font-mono text-default-900">
            {data}
          </pre>
        );
      }
    }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="3xl"
      scrollBehavior="inside"
      aria-label={`Preview of ${file.name}`}
    >
      <ModalContent>
        <ModalHeader className="flex flex-col gap-0.5">
          <span
            className="font-mono text-sm font-semibold text-primary wrap-break-word"
            title={file.path}
          >
            {file.name}
          </span>
          <span className="text-xs font-normal text-default-600">
            {formatBytes(file.size_bytes)}
          </span>
        </ModalHeader>
        <ModalBody className="pt-0">{body}</ModalBody>
        <ModalFooter>
          <Button variant="light" onPress={onClose}>
            Close
          </Button>
          <Button
            as="a"
            href={resourceDownloadUrl(resourceId, file.path)}
            download
            color="primary"
            startContent={<ArrowDownTrayIcon className="size-4" />}
          >
            Download
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
