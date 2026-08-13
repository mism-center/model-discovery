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
import {
  DocumentMagnifyingGlassIcon,
  EyeSlashIcon,
} from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';
import Papa from 'papaparse';

import {
  resourceDownloadUrl,
  TEXT_PREVIEW_MAX_BYTES,
  type ResourceFileItem,
} from '~/api';
import { resourceFileTextQueryOptions } from '~/api/query/resources';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { EmptyState } from '~/components/common/empty-state';
import { formatBytes } from '~/utils/format';

// Heavy renderers are lazy-loaded so they (and Prism/its grammars) stay out of
// the route/SSR bundle; the modal body only mounts after a client click, so
// they never run on the server. Keep this a pure `import(...)` — a static
// import from file-preview-syntax here would defeat the code-split.
const MarkdownPreview = lazy(() => import('./file-preview-markdown'));
const CodePreview = lazy(() => import('./file-preview-syntax'));

/**
 * Extension → Prism language.
 *
 * Names are refractor's, as spelled by the async loader that
 * file-preview-syntax.tsx pulls grammars from — note that hyphenated grammars
 * are camelCase there (`goModule`, not `go-module`). Any of refractor's ~300
 * grammars can be named; nothing has to be registered first, and a name with no
 * grammar renders unhighlighted rather than throwing.
 *
 * Grouped by family rather than alphabetized, because the failure mode here is
 * an omission, not a lookup: `jsx` without `mjs`, or `java` without `kt`, is
 * invisible in an alphabetical list and obvious in a row.
 */
// prettier-ignore
const PRISM_LANGUAGES: Record<string, string> = {
  // Shell and terminal scripting
  sh: 'bash', bash: 'bash', zsh: 'bash', ksh: 'bash', fish: 'bash',
  bat: 'batch', cmd: 'batch',
  ps1: 'powershell', psm1: 'powershell', psd1: 'powershell',
  awk: 'awk', tcl: 'tcl', vim: 'vim',

  // Python, and the file types that are Python by another name
  py: 'python', pyi: 'python', pyw: 'python', pyx: 'python',
  smk: 'python', // Snakemake rules
  ipynb: 'json', // Raw notebook JSON: not a rendered notebook, but readable

  // Scientific and statistical computing
  r: 'r', jl: 'julia', m: 'matlab', sas: 'sas', do: 'stata', stan: 'stan',
  f: 'fortran', for: 'fortran', ftn: 'fortran', f90: 'fortran',
  f95: 'fortran', f03: 'fortran', f08: 'fortran',
  nb: 'wolfram', wl: 'wolfram', wls: 'wolfram',
  cu: 'cpp', cuh: 'cpp', glsl: 'glsl', vert: 'glsl', frag: 'glsl',

  // Compiled and systems languages
  c: 'c', h: 'c',
  cpp: 'cpp', cxx: 'cpp', cc: 'cpp', hpp: 'cpp', hxx: 'cpp', hh: 'cpp',
  rs: 'rust', go: 'go', zig: 'zig', nim: 'nim', d: 'd',
  cs: 'csharp', vb: 'visual-basic', fs: 'fsharp', fsx: 'fsharp', fsi: 'fsharp',
  java: 'java', kt: 'kotlin', kts: 'kotlin', scala: 'scala',
  swift: 'swift', dart: 'dart', mm: 'objectivec',

  // Dynamic and functional languages
  rb: 'ruby', rake: 'ruby', gemspec: 'ruby', ru: 'ruby',
  pl: 'perl', pm: 'perl', php: 'php', lua: 'lua',
  ex: 'elixir', exs: 'elixir', erl: 'erlang', hrl: 'erlang',
  hs: 'haskell', ml: 'ocaml', mli: 'ocaml',
  clj: 'clojure', cljs: 'clojure', cljc: 'clojure', edn: 'clojure',
  lisp: 'lisp', cl: 'lisp', el: 'lisp', scm: 'scheme', ss: 'scheme',
  rkt: 'racket',
  groovy: 'groovy', gradle: 'gradle',
  nf: 'groovy', // Nextflow pipelines

  // Web
  js: 'javascript', mjs: 'javascript', cjs: 'javascript',
  ts: 'typescript', mts: 'typescript', cts: 'typescript',
  jsx: 'jsx', tsx: 'tsx',
  html: 'markup', htm: 'markup', xhtml: 'markup', vue: 'markup',
  css: 'css', scss: 'scss', sass: 'sass', less: 'less', styl: 'stylus',
  graphql: 'graphql', gql: 'graphql',

  // Structured data
  json: 'json', jsonl: 'json', ndjson: 'json', jsonc: 'json',
  geojson: 'json', avsc: 'json', json5: 'json5',
  yaml: 'yaml', yml: 'yaml',
  cff: 'yaml', // Citation File Format
  cwl: 'yaml', // Common Workflow Language
  toml: 'toml',
  proto: 'protobuf', sql: 'sql', ddl: 'sql', psql: 'sql',

  // XML dialects, including the model-exchange formats
  xml: 'markup', xsd: 'markup', xsl: 'markup', xslt: 'markup',
  xaml: 'markup', plist: 'markup', rss: 'markup',
  sbml: 'markup', cellml: 'markup', sedml: 'markup',
  neuroml: 'markup', nml: 'markup',

  // Config, build, and infrastructure
  ini: 'ini', cfg: 'ini', conf: 'ini', cnf: 'ini', properties: 'properties',
  mk: 'makefile', mak: 'makefile', make: 'makefile', cmake: 'cmake',
  dockerfile: 'docker', hcl: 'hcl', tf: 'hcl', tfvars: 'hcl',
  service: 'systemd', socket: 'systemd', timer: 'systemd',

  // Prose, markup, and output
  tex: 'latex', sty: 'latex', cls: 'latex', ltx: 'latex', bib: 'latex',
  rst: 'rest', diff: 'diff', patch: 'diff', log: 'log',
};

/**
 * Files with no extension, or whose name means more than their extension.
 * Keyed by lowercased filename and checked before the extension map, so
 * `CMakeLists.txt` is CMake rather than an unhighlighted `.txt`.
 */
// prettier-ignore
const PRISM_LANGUAGES_BY_FILENAME: Record<string, string> = {
  // Build and task runners
  makefile: 'makefile', gnumakefile: 'makefile', 'cmakelists.txt': 'cmake',
  dockerfile: 'docker', 'containerfile': 'docker',
  rakefile: 'ruby', gemfile: 'ruby', guardfile: 'ruby', podfile: 'ruby',
  vagrantfile: 'ruby', brewfile: 'ruby',
  jenkinsfile: 'groovy',
  snakefile: 'python',
  'go.mod': 'go-module',

  // Lockfiles, named individually: `.lock` says nothing about format. These
  // three are TOML, but yarn.lock has its own syntax, flake.lock is JSON and
  // Gemfile.lock is neither, so the extension can't be mapped as a class.
  'cargo.lock': 'toml', 'poetry.lock': 'toml', 'uv.lock': 'toml',
  pipfile: 'toml',

  // Dotfiles
  '.env': 'ini', '.gitconfig': 'ini', '.editorconfig': 'editorconfig',
  '.bashrc': 'bash', '.bash_profile': 'bash', '.zshrc': 'bash',
  '.profile': 'bash',
  '.gitignore': 'ignore', '.dockerignore': 'ignore', '.npmignore': 'ignore',
  '.prettierignore': 'ignore', '.eslintignore': 'ignore',
  'nginx.conf': 'nginx',
};

export type PreviewCategory =
  | 'image'
  | 'table'
  | 'markdown'
  | 'code'
  | 'text'
  | null;

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp']);
const TABLE_EXTS = new Set(['csv', 'tsv']);
// rmd/qmd are markdown with executable code chunks; rendering the prose is
// closer to their intent than showing the source.
const MARKDOWN_EXTS = new Set(['md', 'markdown', 'mdown', 'rmd', 'qmd']);

/**
 * Extensions whose bytes aren't text. Download-only; no preview.
 *
 * This is a denylist because the previewable side is unenumerable: a model repo
 * brings .py, .sh, .ini, .bib, .rst, .cff, .jl, extensionless LICENSE and
 * Makefile, and whatever the next one brings. Every extension missing from an
 * allowlist is a file the user can't open. Binary formats, by contrast, are a
 * closed set — and anything that slips through is caught by `looksBinary` once
 * its bytes arrive.
 *
 * Kept grouped rather than one-per-line (hence the prettier-ignore): sixty
 * single-token lines are harder to scan for a missing format than five rows.
 */
// prettier-ignore
const BINARY_EXTS = new Set([
  // Archives
  '7z', 'bz2', 'gz', 'jar', 'rar', 'tar', 'tgz', 'whl', 'xz', 'zip', 'zst',
  // Serialized data, arrays, and trained models
  'arrow', 'db', 'feather', 'h5', 'hdf5', 'mat', 'nc', 'npy', 'npz', 'onnx',
  'parquet', 'pb', 'pickle', 'pkl', 'pt', 'pth', 'rds', 'sqlite', 'xls', 'xlsx',
  // Documents and media (PDFs included: no in-app viewer, download instead)
  'avi', 'doc', 'docx', 'ico', 'mov', 'mp3', 'mp4', 'pdf', 'ppt', 'pptx', 'psd',
  'tif', 'tiff', 'wav', 'webm',
  // Compiled artifacts
  'a', 'bin', 'class', 'dll', 'dylib', 'exe', 'o', 'pyc', 'pyd', 'so', 'wasm',
]);

function filenameOf(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1).toLowerCase();
}

/**
 * Lowercased extension, or `''` when there is none.
 *
 * A leading dot doesn't count: `.gitignore` is a dotfile, not a file with a
 * `gitignore` extension. Naive `split('.').pop()` reported `LICENSE` as having
 * extension `license`, which quietly tested filenames against extension sets.
 */
function extensionOf(path: string): string {
  const name = filenameOf(path);
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(dot + 1) : '';
}

/** The Prism grammar for a path, or `'text'` when we have none. */
function prismLanguageForPath(path: string): string {
  return (
    PRISM_LANGUAGES_BY_FILENAME[filenameOf(path)] ??
    PRISM_LANGUAGES[extensionOf(path)] ??
    'text'
  );
}

/** Classify a file for previewing; `null` means "not previewable". */
export function previewCategory(path: string): PreviewCategory {
  const ext = extensionOf(path);
  if (IMAGE_EXTS.has(ext)) return 'image';
  if (BINARY_EXTS.has(ext)) return null;
  if (TABLE_EXTS.has(ext)) return 'table';
  if (MARKDOWN_EXTS.has(ext)) return 'markdown';
  // Anything left is text; having a grammar is the only thing separating a
  // highlighted view from a plain one.
  return prismLanguageForPath(path) === 'text' ? 'text' : 'code';
}

/**
 * Whether decoded content looks like binary rather than text.
 *
 * The cost of the denylist above is that an unrecognized binary extension gets
 * fetched and rendered as mojibake. This catches it after the fact: NUL bytes
 * don't occur in text, and a scattering of U+FFFD means the bytes weren't valid
 * UTF-8. A 2% threshold tolerates a stray mis-encoded character in an otherwise
 * readable file — a latin-1 accent in a comment shouldn't hide the whole file.
 */
function looksBinary(content: string): boolean {
  const sample = content.slice(0, 4096);
  if (sample.length === 0) return false;
  if (sample.includes('\u0000')) return true;
  return (sample.match(/\uFFFD/g)?.length ?? 0) > sample.length * 0.02;
}

const MAX_TABLE_ROWS = 500;

/**
 * Caps on the highlighted preview. Prism emits a React element per token with
 * its own inline style object, so render cost is linear in source length and
 * steep — roughly 1.6 ms per line.
 *
 * MAX_CODE_CHARS catches what the line cap can't: minified files, where 500
 * lines is still megabytes.
 */
const MAX_CODE_LINES = 500;
const MAX_CODE_CHARS = 40_000;

/** Clip content to what we're willing to highlight. */
function clipForHighlight(content: string): {
  text: string;
  truncated: boolean;
} {
  let text = content.split('\n', MAX_CODE_LINES).join('\n');
  if (text.length > MAX_CODE_CHARS) text = text.slice(0, MAX_CODE_CHARS);
  return { text, truncated: text.length !== content.length };
}

/**
 * Whether anything but whitespace remains at or after `index`.
 *
 * Scanning rather than `slice(index).trim()`, which would copy the entire
 * unparsed tail — up to the full file — just to ask a yes/no question. This
 * returns on the first real character, which for a truncated file is
 * immediately.
 */
function hasNonBlankAfter(text: string, index: number): boolean {
  for (let i = index; i < text.length; i++) {
    const ch = text[i];
    if (ch !== ' ' && ch !== '\t' && ch !== '\n' && ch !== '\r') return true;
  }
  return false;
}

/**
 * Render CSV/TSV text as a scrollable HTML table (first row as header).
 *
 * `preview` stops the parser once it has the rows we intend to draw, rather
 * than materializing every row of a file that may be MAX_TEXT_PREVIEW_BYTES
 * long and then discarding all but 500.
 *
 * Do not add `skipEmptyLines`: Papa applies `preview` to raw rows *before*
 * skipping, so a sheet padded with blank lines stops short and reads as
 * complete. Blanks are filtered here instead.
 */
function CsvTable({ content, tsv }: { content: string; tsv: boolean }) {
  const { header, body, hasMore } = useMemo(() => {
    // One row past what we draw.
    const parsed = Papa.parse<string[]>(content, {
      delimiter: tsv ? '\t' : '',
      preview: MAX_TABLE_ROWS + 2,
    });
    const rows = parsed.data.filter(
      (row) => !(row.length === 1 && row[0].trim() === '')
    );
    const [first, ...rest] = rows;

    return {
      header: first,
      body: rest.slice(0, MAX_TABLE_ROWS),
      // Blank lines burn preview budget without producing rows, so a
      // truncated sheet can yield under 500. `meta.cursor` settles it.
      hasMore:
        rest.length > MAX_TABLE_ROWS ||
        hasNonBlankAfter(content, parsed.meta.cursor),
    };
  }, [content, tsv]);

  if (header === undefined) {
    return <p className="text-xs text-default-600">This file is empty.</p>;
  }

  return (
    <div className="flex flex-col">
      {/* The sticky header positions against this element; keep `overflow-auto`
      here. */}
      <div
        className={`max-h-[60vh] overflow-auto border border-default-200 ${
          hasMore ? 'rounded-t-lg' : 'rounded-lg'
        }`}
      >
        <table className="min-w-full border-separate border-spacing-0 text-xs">
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
            {body.map((row, r) => (
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
      {hasMore && (
        <p className="rounded-b-lg border-x border-b border-default-200 bg-default-100 px-3 py-1.5 text-xs text-default-700">
          Showing first {body.length} rows. Download the file to see everything.
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
  const { data, isLoading, isError, error, refetch } = useQuery({
    ...resourceFileTextQueryOptions(resourceId, file.path),
    enabled: isOpen && category !== 'image' && category !== null && !tooLarge,
  });

  /**
   * Binary data (or suspected binary data) = unpreviewable.
   */
  const unpreviewable =
    category === null || (data !== undefined && looksBinary(data));

  let body: React.ReactNode;
  if (category === 'image') {
    body = (
      <img
        src={resourceDownloadUrl(resourceId, file.path, { inline: true })}
        alt={file.name}
        className="mx-auto block min-h-0 max-w-full rounded-lg object-contain"
      />
    );
  } else if (unpreviewable) {
    // Ahead of `tooLarge`: an unshowable format is the reason, not the size.
    body = (
      <EmptyState
        icon={EyeSlashIcon}
        title="No preview available"
        description="This file's format can't be displayed in the browser."
      />
    );
  } else if (tooLarge) {
    body = (
      <EmptyState
        icon={DocumentMagnifyingGlassIcon}
        title="Too large to preview"
        description="Download this file to view its contents."
      />
    );
  } else if (isLoading) {
    body = (
      <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-default-600">
        <Spinner size="sm" />
        <span>Loading preview…</span>
      </div>
    );
  } else if (isError || data === undefined) {
    // The same component the Files section uses when its listing fails, so a
    // failed preview reads as the same kind of event: it classifies the error
    // (offline, 401, 5xx), offers a retry, and surfaces details in dev.
    body = (
      <ApiErrorDisplay
        error={error}
        title="Couldn't load this file"
        onRetry={() => void refetch()}
      />
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
              <MarkdownPreview>{data}</MarkdownPreview>
            </div>
          </Suspense>
        );

        break;
      }
      case 'code': {
        const { text, truncated } = clipForHighlight(data);
        body = (
          <Suspense fallback={<Spinner size="sm" />}>
            <div className="flex flex-col">
              <div
                className={`overflow-auto border border-default-200 bg-default-50 p-3 ${
                  truncated ? 'rounded-t-lg' : 'rounded-lg'
                }`}
              >
                <CodePreview language={prismLanguageForPath(file.path)}>
                  {text}
                </CodePreview>
              </div>
              {truncated && (
                <p className="rounded-b-lg border-x border-b border-default-200 bg-default-100 px-3 py-1.5 text-xs text-default-700">
                  Showing the beginning of this file. Download it to see
                  everything.
                </p>
              )}
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
          <span className="text-xs font-normal text-default-700">
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
