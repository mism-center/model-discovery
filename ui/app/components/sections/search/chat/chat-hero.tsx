import { SparklesIcon } from '@heroicons/react/16/solid';
import cn from 'classnames';

const EXAMPLE_QUESTIONS = [
  'What models describe HIV and CD4 T-cell interaction dynamics?',
  'Which tools simulate multiscale tissue mechanics and agent-based cell behaviour?',
  'How is tumour growth modelled under immune checkpoint inhibition?',
  'What models capture circadian rhythm oscillation in mammals?',
];

/**
 * Collapses on the first question. The transition mirrors the one
 * `search-bar/search-bar.tsx` runs, so the two Discover surfaces behave
 * identically.
 */
export function ChatHero({
  isCollapsed,
  animate,
  onAsk,
}: {
  isCollapsed: boolean;
  /**
   * False until restored history has painted. Collapsing to match what was
   * already on disk is not a state change the user made, so it must not be
   * animated on load.
   */
  animate: boolean;
  onAsk: (question: string) => void;
}) {
  return (
    <div
      className={cn(
        'grid',
        isCollapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]'
      )}
      style={{
        transitionProperty: animate ? 'grid-template-rows' : 'none',
        transitionDuration: '300ms',
        transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      <div
        className="overflow-hidden"
        style={{
          opacity: isCollapsed ? 0 : 1,
          transitionProperty: animate ? 'opacity' : 'none',
          transitionDuration: '200ms',
          transitionTimingFunction: 'ease-in-out',
        }}
      >
        {/*
         * Fills the viewport by its own min-height rather than by flex-grow:
         * a `grow` that toggles with `isCollapsed` re-runs flex layout during
         * the grid-rows transition, which is what made the collapse stutter.
         * 11rem is the sticky header plus the composer.
         */}
        <div className="relative flex min-h-[calc(100dvh-11rem)] flex-col justify-center border-b border-default bg-primary-gradient py-14">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.025]"
            style={{
              backgroundImage: `linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)`,
              backgroundSize: '40px 40px',
            }}
          />

          <div className="relative z-10 mx-auto w-full max-w-[1080px] px-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex shrink-0 items-center justify-center rounded-lg border border-success/20 bg-success/15 p-2 text-success">
                <SparklesIcon className="size-5" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-success">
                AI Mode
              </span>
            </div>

            <h1 className="mb-4 font-headline text-4xl leading-[1.1] tracking-tight text-white md:text-5xl">
              Ask about{' '}
              <span className="text-gradient-success-secondary">models</span> &{' '}
              <span className="text-gradient-success-secondary">tools</span> in
              plain language
            </h1>

            <p className="mb-8 max-w-[62ch] text-[15px] font-light leading-relaxed text-slate-300">
              Answers are drawn from the BioModels repository and a curated tool
              catalogue, with the matching records listed beneath each answer.
            </p>

            <ul className="grid gap-3 sm:grid-cols-2">
              {EXAMPLE_QUESTIONS.map((question) => (
                <li key={question}>
                  <button
                    className={cn(
                      'h-full w-full rounded-lg border border-white/20 bg-white/10 p-4 text-left',
                      'text-sm font-light leading-relaxed text-slate-200 backdrop-blur-md',
                      'transition-colors duration-300 motion-reduce:transition-none',
                      'hover:border-white/30 hover:bg-white/[0.14] hover:text-white'
                    )}
                    onClick={() => onAsk(question)}
                    type="button"
                  >
                    {question}
                  </button>
                </li>
              ))}
            </ul>

            <p className="mt-8 text-xs font-light text-slate-400">
              Answers are AI generated. Check the linked records before relying
              on one.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
