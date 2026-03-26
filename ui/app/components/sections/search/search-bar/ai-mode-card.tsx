import { ArrowRightIcon, SparklesIcon } from '@heroicons/react/16/solid';
import { Link } from '@heroui/react';
import cn from 'classnames';

export function AIModeCard() {
  return (
    <Link
      href="/chat"
      className={cn(
        'block relative group shrink-0 transition-all duration-500',
        'w-full h-full min-w-70 md:min-w-80',
        'hover:opacity-100! hover:scale-[1.01] hover:-translate-y-0.5 active:scale-[0.99]'
      )}
    >
      <div
        className={cn(
          'relative h-full p-5 rounded-xl',
          'bg-white/10 border border-white/20 backdrop-blur-md',
          'shadow-lg shadow-glass',
          'group-hover:bg-white/12.5 group-hover:border-white/30',
          'transition-all duration-500'
        )}
      >
        <div className="flex items-center gap-3 mb-4">
          <div
            className={cn(
              'flex items-center justify-center shrink-0',
              'p-2 rounded-lg bg-success/15 border border-success/20 text-success'
            )}
          >
            <SparklesIcon className="size-5" />
          </div>
          <div>
            <span className="text-xs font-bold text-success tracking-wider uppercase">
              AI Mode
            </span>
          </div>
        </div>

        <h3 className="text-lg font-semibold text-white leading-snug mb-2">
          Complex query? Use natural language.
        </h3>
        <p className="text-sm font-light text-slate-300 mb-4 leading-relaxed">
          Refine and synthesize your search results. Describe your research
          focus and let us find the connections for you.
        </p>

        <div
          className={cn(
            'flex items-center justify-between w-full',
            'whitespace-nowrap gap-3 shrink-0',
            'font-bold text-sm text-white group-hover:text-success',
            'transition-colors duration-500'
          )}
        >
          Launch Assistant
          <div
            className={cn(
              'inline-flex items-center justify-center shrink-0',
              'w-8 h-8 rounded-full',
              'bg-white/10 group-hover:bg-success/20'
            )}
          >
            <ArrowRightIcon className="size-4" />
          </div>
        </div>
      </div>
    </Link>
  );
}