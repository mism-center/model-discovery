import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';

import {
  ask,
  cancel,
  isGenerating,
  retry,
  useChatState,
} from '~/chat/state/chat-store';
import { ChatComposer } from './chat/chat-composer';
import { ChatHero } from './chat/chat-hero';
import { ChatTurnView } from './chat/chat-turn';

export default function ChatSection() {
  const state = useChatState();
  const [searchParams] = useSearchParams();

  const [conversationId, setConversationId] = useState<string | null>(null);
  // `?q=` prefills the composer once and never sends on its own.
  const [draft, setDraft] = useState(() => searchParams.get('q') ?? '');

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);

  const conversation = conversationId
    ? state.conversations[conversationId]
    : undefined;
  const turns = conversation?.turns ?? [];
  const generating = isGenerating(conversation);

  /**
   * Bring a newly asked question to the top of the viewport.
   *
   * Keyed on the turn count, so only asking scrolls. An answer arriving must
   * not move the page: it can land minutes later, against a conversation the
   * reader has since scrolled away from.
   *
   * Positioning is instant because Chrome silently drops smooth scrolling in a
   * tab that is not focused, which is exactly when a slow answer returns.
   */
  const previousTurnCount = useRef(turns.length);
  useEffect(() => {
    if (turns.length > previousTurnCount.current) {
      lastTurnRef.current?.scrollIntoView({ block: 'start' });
    }
    previousTurnCount.current = turns.length;
  }, [turns.length]);

  function submit(question: string) {
    const id = ask(conversationId, question);
    if (id !== conversationId) setConversationId(id);
    setDraft('');
    textareaRef.current?.focus();
  }

  function cancelCurrent() {
    if (conversationId) cancel(conversationId);
    textareaRef.current?.focus();
  }

  return (
    <main className="flex grow flex-col bg-white">
      <ChatHero isCollapsed={turns.length > 0} onAsk={submit} />

      <div
        aria-live="polite"
        aria-relevant="additions"
        className="mx-auto w-full max-w-[1080px] grow px-6 empty:px-0"
        role="log"
      >
        {turns.length > 0 ? (
          <div className="py-10">
            {turns.map((turn, index) => (
              <div
                className="scroll-mt-20"
                key={turn.id}
                ref={index === turns.length - 1 ? lastTurnRef : undefined}
              >
                <ChatTurnView
                  onCancel={cancelCurrent}
                  onRetry={() => {
                    if (conversationId) retry(conversationId, turn.id);
                  }}
                  turn={turn}
                />
              </div>
            ))}
          </div>
        ) : undefined}
      </div>

      <ChatComposer
        isGenerating={generating}
        onCancel={cancelCurrent}
        onChange={setDraft}
        onSubmit={() => submit(draft)}
        textareaRef={textareaRef}
        value={draft}
      />
    </main>
  );
}
