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
import { ThreadSkeleton } from './chat/thread-skeleton';
import { ChatTurnView } from './chat/chat-turn';

/** Search param naming the conversation on screen. */
const CONVERSATION_PARAM = 'c';

export default function ChatSection() {
  const state = useChatState();
  const [searchParams, setSearchParams] = useSearchParams();

  /**
   * The conversation being viewed lives in the URL, so it is known on the very
   * first render. Holding it in component state instead meant the empty state
   * painted before IndexedDB answered, then flipped to a restored thread.
   */
  const conversationId = searchParams.get(CONVERSATION_PARAM);

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

  function viewConversation(id: string | null) {
    setSearchParams(
      (params) => {
        if (id) params.set(CONVERSATION_PARAM, id);
        else params.delete(CONVERSATION_PARAM);
        return params;
      },
      { replace: true, preventScrollReset: true }
    );
  }

  const [animateHero, setAnimateHero] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);
  useEffect(() => {
    void hydrate().then(() => {
      setIsHydrated(true);
      // A frame later, so restored history paints before transitions are armed
      // and the hero does not animate shut on load.
      requestAnimationFrame(() => setAnimateHero(true));
    });
  }, []);

  /**
   * Scrolling, for the two cases that need it and no others.
   *
   * Opening a different conversation starts at its top. Asking within the
   * conversation on screen brings the new question up. Both are tracked
   * together because a switch also changes the turn count, and treating that
   * as "a question was asked" scrolls the reader to the bottom of a thread
   * they just opened.
   *
   * An answer arriving never scrolls: it can land minutes later, against a
   * conversation the reader has since navigated away from. Positioning is
   * instant because Chrome drops smooth scrolling in an unfocused tab, which
   * is exactly when a slow answer returns.
   */
  const viewed = useRef({ id: conversationId, turnCount: turns.length });
  useEffect(() => {
    const previous = viewed.current;
    viewed.current = { id: conversationId, turnCount: turns.length };

    if (previous.id !== conversationId) {
      globalThis.scrollTo({ top: 0 });
      return;
    }
    if (turns.length > previous.turnCount) {
      lastTurnRef.current?.scrollIntoView({ block: 'start' });
    }
  }, [conversationId, turns.length]);

  function submit(question: string) {
    const id = ask(conversationId, question);
    if (id !== conversationId) viewConversation(id);
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
    viewConversation(null);
    setDraft('');
    textareaRef.current?.focus();
  }

  function deleteConversation(id: string) {
    removeConversation(id);
    if (id === conversationId) viewConversation(null);
  }

  /*
   * A conversation named in the URL has no turns until IndexedDB answers, so
   * that window shows the thread's shape instead of the empty state. The hero
   * stays collapsed through it rather than flashing over a thread that is
   * about to appear.
   */
  const isLoadingConversation = conversationId !== null && !isHydrated;
  const heroCollapsed = turns.length > 0 || isLoadingConversation;

  return (
    <main className="flex grow bg-white">
      <ChatSidebar
        activeId={conversationId ?? undefined}
        conversations={conversations}
        onDelete={deleteConversation}
        onNewChat={startNewChat}
        onSelect={viewConversation}
      />

      <div className="relative flex min-w-0 grow flex-col">
        {/*
         * Spans the whole column, composer included, so the hero's navy runs to
         * the bottom of the page and its radial gradients are anchored to the
         * page's own corners. It cross-fades because a `background-image`
         * cannot be transitioned between states on a single element.
         */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-primary-gradient"
          style={{
            opacity: heroCollapsed ? 0 : 1,
            transitionProperty: animateHero ? 'opacity' : 'none',
            transitionDuration: '300ms',
            transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          <div
            className="absolute inset-0 opacity-[0.025]"
            style={{
              backgroundImage: `linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)`,
              backgroundSize: '40px 40px',
            }}
          />
        </div>

        <ChatHero
          animate={animateHero}
          isCollapsed={heroCollapsed}
          onAsk={submit}
        />

        {/*
         * Always grows. Without it the column has nothing to fill the viewport
         * while a URL-named conversation is still being read from IndexedDB,
         * and the sticky composer rides up under the header.
         */}
        <div
          aria-live="polite"
          aria-relevant="additions"
          className="relative z-10 mx-auto w-full max-w-[1080px] grow px-6"
          role="log"
        >
          {isLoadingConversation ? <ThreadSkeleton /> : undefined}

          {turns.length > 0 ? (
            <div className="py-10">
              {turns.map((turn, index) => (
                <div
                  className="scroll-mt-20 pb-8 last:pb-0"
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
          isOnHero={!heroCollapsed}
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
