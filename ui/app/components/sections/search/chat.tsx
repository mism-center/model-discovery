import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';

import {
  ask,
  cancel,
  conversationList,
  hydrate,
  isGenerating,
  removeConversation,
  retry,
  useChatState,
} from '~/chat/state/chat-store';
import { ChatComposer } from './chat/chat-composer';
import { ChatHero } from './chat/chat-hero';
import { ChatSidebar } from './chat/chat-sidebar';
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
  const conversations = conversationList(state);

  /**
   * Reading from IndexedDB is async, so history arrives after first paint.
   * Opening the most recent conversation only if none is active leaves a
   * conversation started before hydration finished untouched.
   */
  const [animateHero, setAnimateHero] = useState(false);
  useEffect(() => {
    void hydrate().then((id) => {
      if (id) setConversationId((current) => current ?? id);
      // A frame later, so the restored state paints before transitions are
      // armed and the hero does not animate shut on every reload.
      requestAnimationFrame(() => setAnimateHero(true));
    });
  }, []);

  /**
   * Bring a newly asked question to the top of the viewport.
   *
   * Keyed on the turn count of the conversation being viewed, so only asking
   * scrolls. An answer arriving must not move the page: it can land minutes
   * later, against a conversation the reader has since navigated away from.
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

  function startNewChat() {
    // No conversation is created until a question is asked, so the history
    // never fills with entries that were opened and never used.
    setConversationId(null);
    setDraft('');
    textareaRef.current?.focus();
  }

  function deleteConversation(id: string) {
    removeConversation(id);
    if (id === conversationId) setConversationId(null);
  }

  return (
    <main className="flex grow bg-white">
      <ChatSidebar
        activeId={conversationId ?? undefined}
        conversations={conversations}
        onDelete={deleteConversation}
        onNewChat={startNewChat}
        onSelect={setConversationId}
      />

      <div className="flex min-w-0 grow flex-col">
        <ChatHero
          animate={animateHero}
          isCollapsed={turns.length > 0}
          onAsk={submit}
        />

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
      </div>
    </main>
  );
}
