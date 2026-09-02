import { type RefObject, useEffect } from 'react';
import { ArrowUpIcon } from '@heroicons/react/16/solid';
import { Button } from '@heroui/react';
import cn from 'classnames';

const MAX_TEXTAREA_HEIGHT = 200;

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  onCancel,
  isGenerating,
  isOnHero,
  textareaRef,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isGenerating: boolean;
  /**
   * The hero's navy runs behind the tray, so every surface here has to drop
   * out and the text has to invert.
   */
  isOnHero: boolean;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}) {
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [value, textareaRef]);

  const canSend = value.trim().length > 0 && !isGenerating;

  return (
    <div
      className={cn(
        'sticky bottom-0 z-20 border-t backdrop-blur-sm',
        'transition-colors duration-300 motion-reduce:transition-none',
        isOnHero
          ? 'border-transparent bg-transparent'
          : 'border-default-200 bg-white/95'
      )}
    >
      <div className="mx-auto w-full max-w-[1080px] px-6 py-4">
        <form
          className={cn(
            // The textarea carries no inset of its own, so the text and the
            // send button are both `px-3` off the border.
            'flex items-end gap-2 rounded-lg border px-3 py-2.5',
            'transition-colors duration-300 motion-reduce:transition-none',
            'focus-within:ring-2',
            isOnHero
              ? 'border-white/20 bg-white/10 backdrop-blur-md focus-within:ring-white/30'
              : 'border-default-200 bg-white focus-within:ring-slate-300'
          )}
          onSubmit={(event) => {
            event.preventDefault();
            if (canSend) onSubmit();
          }}
        >
          <textarea
            aria-label="Ask a question about models and tools"
            // `py-1` puts a single row at 32px, matching the send button, so
            // the two sit on one line until the field actually grows.
            className={cn(
              'max-h-50 flex-1 resize-none bg-transparent py-1 text-[15px] leading-6 outline-none',
              'transition-colors duration-300 motion-reduce:transition-none',
              isOnHero
                ? 'text-white placeholder:text-slate-400'
                : 'text-default-900 placeholder:text-default-800'
            )}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (canSend) onSubmit();
                return;
              }
              if (event.key === 'Escape' && isGenerating) {
                event.preventDefault();
                onCancel();
              }
            }}
            placeholder="Ask about models, mechanisms, or tools…"
            ref={textareaRef}
            rows={1}
            value={value}
          />
          <Button
            aria-label="Send question"
            color={isOnHero ? 'default' : 'primary'}
            isDisabled={!canSend}
            isIconOnly
            radius="full"
            size="sm"
            type="submit"
          >
            <ArrowUpIcon className="size-4" />
          </Button>
        </form>
        <p
          className={cn(
            'mt-2 text-[11px]',
            'transition-colors duration-300 motion-reduce:transition-none',
            isOnHero ? 'text-slate-400' : 'text-default-800'
          )}
        >
          Enter to send · Shift + Enter for a new line · Answers are AI
          generated. Check the linked records before relying on one.
        </p>
      </div>
    </div>
  );
}
