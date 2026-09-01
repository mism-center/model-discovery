import { useEffect, useState } from 'react';
import { Button, Spinner } from '@heroui/react';
import cn from 'classnames';

import type { ChatTurn } from '~/chat/state/types';
import { AnswerMarkdown } from './answer-markdown';
import { EvidenceList } from './evidence-list';

const SLOW_ANSWER_MS = 45_000;

/**
 * Whether the wait has run long enough to be worth reassuring the user about.
 *
 * A single timeout rather than a ticking elapsed counter: nothing here displays
 * seconds, so re-rendering the thread once a second would buy nothing.
 */
function useSlowNotice(active: boolean): boolean {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!active) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), SLOW_ANSWER_MS);
    return () => clearTimeout(timer);
  }, [active]);

  return slow;
}

function MetaAction({
  children,
  onPress,
}: {
  children: React.ReactNode;
  onPress: () => void;
}) {
  return (
    <button
      className="text-default-800 underline underline-offset-2 hover:text-primary"
      onClick={onPress}
      type="button"
    >
      {children}
    </button>
  );
}

function AnswerMeta({
  turn,
  onAskAgain,
}: {
  turn: ChatTurn;
  onAskAgain: () => void;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  const sources = turn.evidence?.length ?? 0;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-default-800">
      {turn.elapsedSeconds === undefined ? undefined : (
        <>
          <span>Answered in {turn.elapsedSeconds.toFixed(1)}s</span>
          <span aria-hidden="true">·</span>
        </>
      )}
      <span>
        {sources} {sources === 1 ? 'source' : 'sources'}
      </span>
      <span aria-hidden="true">·</span>
      <MetaAction
        onPress={() => {
          void navigator.clipboard?.writeText(turn.answer ?? '');
          setCopied(true);
        }}
      >
        {copied ? 'Copied' : 'Copy'}
      </MetaAction>
      <span aria-hidden="true">·</span>
      <MetaAction onPress={onAskAgain}>Ask again</MetaAction>
    </div>
  );
}

function PendingAnswer({ onCancel }: { onCancel: () => void }) {
  const slow = useSlowNotice(true);

  return (
    <div className="mt-1">
      <div className="flex items-center gap-3">
        <Spinner color="secondary" size="sm" variant="simple" />
        <span className="text-sm text-default-800">
          Searching models and tools, then writing an answer…
        </span>
      </div>
      {slow ? (
        <p className="mt-2 text-xs text-default-800">
          Complex questions can take up to three minutes.
        </p>
      ) : undefined}
      <Button className="mt-3" onPress={onCancel} size="sm" variant="bordered">
        Cancel
      </Button>
    </div>
  );
}

function FailedAnswer({
  message,
  onRetry,
}: {
  message: string | undefined;
  onRetry: () => void;
}) {
  return (
    <div className="mt-1">
      <p className="text-sm text-danger-600">
        {message ?? 'The request failed before CAIRNS could answer.'}
      </p>
      <Button className="mt-3" onPress={onRetry} size="sm" variant="bordered">
        Try again
      </Button>
    </div>
  );
}

export function ChatTurnView({
  turn,
  onCancel,
  onRetry,
}: {
  turn: ChatTurn;
  onCancel: () => void;
  onRetry: () => void;
}) {
  return (
    <article className="relative pb-12 pl-6 last:pb-0">
      <span
        aria-hidden="true"
        className="absolute left-0 top-0 h-full w-px bg-default-200"
      />

      <div className="relative">
        <span
          aria-hidden="true"
          className="absolute -left-6 top-0 h-full w-0.5 bg-secondary"
        />
        <h2 className="font-headline text-xl text-primary text-balance">
          {turn.question}
        </h2>
      </div>

      <div className={cn('mt-4', turn.status === 'answered' && 'max-w-[68ch]')}>
        {turn.status === 'pending' ? (
          <PendingAnswer onCancel={onCancel} />
        ) : undefined}

        {turn.status === 'failed' ? (
          <FailedAnswer message={turn.error} onRetry={onRetry} />
        ) : undefined}

        {turn.status === 'cancelled' ? (
          <div className="mt-1">
            <p className="text-sm text-default-800">Cancelled.</p>
            <Button
              className="mt-3"
              onPress={onRetry}
              size="sm"
              variant="bordered"
            >
              Resend
            </Button>
          </div>
        ) : undefined}

        {turn.status === 'answered' && turn.answer ? (
          <>
            <AnswerMarkdown cards={turn.evidence ?? []} turnId={turn.id}>
              {turn.answer}
            </AnswerMarkdown>
            <AnswerMeta onAskAgain={onRetry} turn={turn} />
          </>
        ) : undefined}
      </div>

      {turn.status === 'answered' && turn.evidence?.length ? (
        <EvidenceList
          answer={turn.answer ?? ''}
          cards={turn.evidence}
          turnId={turn.id}
        />
      ) : undefined}
    </article>
  );
}
