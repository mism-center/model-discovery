/**
 * Thin wrapper around react-syntax-highlighter's light Prism build.
 *
 * Lives in its own module, imported ONLY via `lazy(() => import(...))` from the
 * preview modal — this keeps Prism and its grammars out of the route bundle and
 * the SSR path. Do not add a static import of this module anywhere, or the
 * code-split breaks. Only the grammars we actually preview are registered,
 * rather than pulling every language Prism ships.
 */
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import yaml from 'react-syntax-highlighter/dist/esm/languages/prism/yaml';
import markup from 'react-syntax-highlighter/dist/esm/languages/prism/markup';
import toml from 'react-syntax-highlighter/dist/esm/languages/prism/toml';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('markup', markup); // xml/html
SyntaxHighlighter.registerLanguage('toml', toml);

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
