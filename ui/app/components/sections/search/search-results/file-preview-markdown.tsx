/**
 * Markdown renderer for the file preview.
 *
 * Its own module, imported ONLY via `lazy(() => import(...))` from the preview
 * modal, so react-markdown and its remark plugins stay out of the route bundle.
 * Do not add a static import of this module anywhere.
 *
 * remark-gfm supplies tables, strikethrough, task lists and autolinks, none of
 * which react-markdown handles on its own.
 */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownPreview({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>;
}
