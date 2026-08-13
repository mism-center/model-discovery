/**
 * Thin wrapper around react-syntax-highlighter's async Prism build.
 *
 * Lives in its own module, imported ONLY via `lazy(() => import(...))` from the
 * preview modal; this keeps the highlighter out of the route bundle and the
 * SSR path. Do not add a static import of this module anywhere.
 *
 * PrismAsyncLight fetches each grammar on its own dynamic import, so
 * previewing a `.py` pulls the python grammar alone. Grammar names are the
 * async loader's, which spells hyphenated ones in camelCase (`goModule`).
 */
import { PrismAsyncLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

export default function CodePreview({
  language,
  children,
}: {
  language: string;
  children: string;
}) {
  return (
    <SyntaxHighlighter
      language={language}
      style={oneLight}
      wrapLongLines
      customStyle={{
        margin: 0,
        background: 'transparent',
        fontSize: '12px',
      }}
      codeTagProps={{ style: { fontSize: '12px' } }}
    >
      {children}
    </SyntaxHighlighter>
  );
}
