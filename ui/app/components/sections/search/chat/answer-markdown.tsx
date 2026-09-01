import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Tailwind's preflight strips default element styling, so every tag CAIRNS can
 * emit needs an entry here or it renders as an undifferentiated run of text.
 *
 * `default` is a light surface ramp: only 800 and 900 clear WCAG AA on white.
 */
const components: Components = {
  p: ({ children }) => (
    <p className="mb-4 leading-7 text-default-900 last:mb-0">{children}</p>
  ),
  h1: ({ children }) => (
    <h1 className="font-headline text-2xl text-primary mt-8 mb-3 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="font-headline text-xl text-primary mt-8 mb-3 first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="font-headline text-base text-primary mt-6 mb-2 first:mt-0">
      {children}
    </h3>
  ),
  ul: ({ children }) => (
    <ul className="mb-4 list-disc pl-5 space-y-2 marker:text-default-800 last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-4 list-decimal pl-5 space-y-2 marker:text-default-800 marker:font-semibold last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="leading-7 text-default-900 pl-1">{children}</li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-primary">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a
      className="text-secondary underline underline-offset-2 hover:text-primary"
      href={href}
      rel="noreferrer noopener"
      target="_blank"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded-xs bg-default-100 px-1.5 py-0.5 font-mono text-[13px] text-default-900">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="mb-4 overflow-x-auto rounded-md bg-default-100 p-4 font-mono text-[13px] text-default-900">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-4 border-l-2 border-secondary pl-4 text-default-800 italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-6 border-default-200" />,
  table: ({ children }) => (
    <div className="mb-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-default-200 px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wide text-default-800">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-default-100 px-3 py-2 align-top text-default-900">
      {children}
    </td>
  ),
};

export function AnswerMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>
      {children}
    </ReactMarkdown>
  );
}
