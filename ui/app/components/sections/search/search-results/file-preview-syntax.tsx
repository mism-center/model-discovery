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
import goModule from 'refractor/go-module';
import visualBasic from 'refractor/visual-basic';
import 'prism-themes/themes/prism-one-light.css';

// The async loader keys these two as `goModule` / `visualBasic` but registers
// them under their real names, so asking for either spelling fails: the
// camelCase one is never registered, and the kebab one has no loader entry.
// Registering them here queues them until the core loads, after which the
// kebab names resolve normally.
SyntaxHighlighter.registerLanguage('go-module', goModule);
SyntaxHighlighter.registerLanguage('visual-basic', visualBasic);

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
      // Emits `class="token keyword"` rather than building a style object per
      // token, which is where nearly all of the render cost lives. Paired with
      // the theme import above: removing either one breaks the other.
      useInlineStyles={false}
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
