import { useSyncExternalStore } from 'react';

import { recommend } from '~/api/endpoints/cairns';
import {
  deleteConversation as deleteStoredConversation,
  loadConversations,
  saveConversation,
} from './chat-storage';
import type { ChatState, ChatTurn, Conversation } from './types';

/** CAIRNS keeps no server-side memory, so the client replays context itself. */
const MAX_REPLAYED_PAIRS = 6;
const MAX_REPLAYED_CHARS = 12_000;

const EMPTY_STATE: ChatState = { conversations: {}, order: [] };

let state: ChatState = EMPTY_STATE;
const listeners = new Set<() => void>();

/**
 * Live requests, keyed by conversation, holding only what cancellation needs.
 *
 * Deliberately outside `state`: an `AbortController` is not renderable data,
 * and keeping it out means the only thing the UI can read is the owning turn's
 * own `status`.
 */
const inFlight = new Map<string, AbortController>();

// ── Subscription ────────────────────────────────────────────────

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): ChatState {
  return state;
}

/**
 * The module is shared by every SSR render on the server, so the server
 * snapshot is a constant rather than `state`.
 */
function getServerSnapshot(): ChatState {
  return EMPTY_STATE;
}

export function useChatState(): ChatState {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

function setState(next: ChatState): void {
  state = next;
  for (const listener of listeners) listener();
}

// ── Derivation ──────────────────────────────────────────────────

export function isGenerating(conversation: Conversation | undefined): boolean {
  return conversation?.turns.some((turn) => turn.status === 'pending') ?? false;
}

// ── Mutation ────────────────────────────────────────────────────

/**
 * An empty conversation is not history. Writing one would fill the stored list
 * with entries the user opened and never used.
 */
function persist(id: string): void {
  const conversation = state.conversations[id];
  if (!conversation || conversation.turns.length === 0) return;
  void saveConversation(conversation);
}

function updateConversation(
  id: string,
  update: (conversation: Conversation) => Conversation
): void {
  const existing = state.conversations[id];
  if (!existing) return;
  setState({
    ...state,
    conversations: { ...state.conversations, [id]: update(existing) },
  });
  persist(id);
}

function updateTurn(
  conversationId: string,
  turnId: string,
  patch: Partial<ChatTurn>
): void {
  updateConversation(conversationId, (conversation) => ({
    ...conversation,
    turns: conversation.turns.map((turn) =>
      turn.id === turnId ? { ...turn, ...patch } : turn
    ),
  }));
}

/**
 * A turn left pending belongs to a request that died with the page, so it can
 * never arrive. It is restored as cancelled, which is resendable, rather than
 * as a spinner that would run forever.
 */
function restored(conversation: Conversation): Conversation {
  if (!conversation.turns.some((turn) => turn.status === 'pending')) {
    return conversation;
  }
  return {
    ...conversation,
    turns: conversation.turns.map((turn) =>
      turn.status === 'pending' ? { ...turn, status: 'cancelled' } : turn
    ),
  };
}

/**
 * Conversation ids, newest first.
 *
 * Built by insertion rather than sorting: `Array#sort` is banned by lint in
 * favour of `toSorted`, which this project's `lib` target does not provide.
 */
function newestFirst(conversations: Record<string, Conversation>): string[] {
  const order: string[] = [];
  for (const conversation of Object.values(conversations)) {
    const index = order.findIndex(
      (id) => conversations[id].createdAt < conversation.createdAt
    );
    if (index === -1) {
      order.push(conversation.id);
    } else {
      order.splice(index, 0, conversation.id);
    }
  }
  return order;
}

let hydrated = false;

/**
 * Merge persisted conversations into the store, newest first.
 *
 * Safe to call more than once and safe to race with `ask`: a conversation
 * created in this session is newer than anything on disk and is left alone.
 * Returns the conversation to open, or undefined when there is no history.
 */
export async function hydrate(): Promise<string | undefined> {
  if (hydrated) return state.order[0];
  hydrated = true;

  const stored = await loadConversations();
  if (stored.length === 0) return state.order[0];

  const conversations = { ...state.conversations };
  for (const conversation of stored) {
    conversations[conversation.id] ??= restored(conversation);
  }

  const order = newestFirst(conversations);
  setState({ conversations, order });
  return order[0];
}

export function createConversation(): string {
  const id = crypto.randomUUID();
  setState({
    ...state,
    conversations: {
      ...state.conversations,
      [id]: { id, createdAt: Date.now(), turns: [] },
    },
    order: [id, ...state.order],
  });
  return id;
}

/**
 * Turns replayed as CAIRNS `chat_history`, oldest first.
 *
 * Only answered turns qualify: a pending, failed or cancelled turn has no
 * assistant half, and sending an empty one would present the failure to the
 * model as something it said. Walks backwards so the caps keep recent context.
 */
function replayableHistory(conversation: Conversation): string[][] {
  const pairs: string[][] = [];
  let characters = 0;

  for (let index = conversation.turns.length - 1; index >= 0; index--) {
    const turn = conversation.turns[index];
    if (turn.status !== 'answered' || !turn.answer) continue;
    if (pairs.length >= MAX_REPLAYED_PAIRS) break;
    characters += turn.question.length + turn.answer.length;
    if (characters > MAX_REPLAYED_CHARS) break;
    pairs.unshift([turn.question, turn.answer]);
  }

  return pairs;
}

function failureMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return 'The request failed before CAIRNS could answer.';
}

async function runTurn(
  conversationId: string,
  turnId: string,
  question: string
): Promise<void> {
  const conversation = state.conversations[conversationId];
  if (!conversation) return;

  const controller = new AbortController();
  inFlight.set(conversationId, controller);

  try {
    const response = await recommend(
      { question, chat_history: replayableHistory(conversation) },
      { signal: controller.signal }
    );
    updateTurn(conversationId, turnId, {
      status: 'answered',
      answer: response.answer,
      evidence: response.evidence ?? [],
      elapsedSeconds: response.elapsed_seconds,
    });
  } catch (error) {
    updateTurn(
      conversationId,
      turnId,
      controller.signal.aborted
        ? { status: 'cancelled' }
        : { status: 'failed', error: failureMessage(error) }
    );
  } finally {
    // A later turn may already own the slot; only the current one clears it.
    if (inFlight.get(conversationId) === controller) {
      inFlight.delete(conversationId);
    }
  }
}

/**
 * Put a question to CAIRNS, creating the conversation if needed.
 *
 * The question is committed to the thread before the request goes out, so a
 * failure leaves something on screen to retry rather than losing what was typed.
 */
export function ask(
  conversationId: string | null,
  question: string
): string | null {
  const trimmed = question.trim();
  // Checked before the conversation is created, so a blank submit cannot leave
  // an empty conversation behind.
  if (!trimmed) return conversationId;

  const id = conversationId ?? createConversation();
  if (inFlight.has(id)) return id;

  const turnId = crypto.randomUUID();
  updateConversation(id, (conversation) => ({
    ...conversation,
    turns: [
      ...conversation.turns,
      { id: turnId, question: trimmed, askedAt: Date.now(), status: 'pending' },
    ],
  }));

  void runTurn(id, turnId, trimmed);
  return id;
}

export function retry(conversationId: string, turnId: string): void {
  const turn = state.conversations[conversationId]?.turns.find(
    (candidate) => candidate.id === turnId
  );
  if (!turn || inFlight.has(conversationId)) return;

  updateTurn(conversationId, turnId, { status: 'pending', error: undefined });
  void runTurn(conversationId, turnId, turn.question);
}

/**
 * Abort the conversation's in-flight request. Only ever called from an explicit
 * user action: unmounting `/chat` must leave a request running.
 */
export function cancel(conversationId: string): void {
  inFlight.get(conversationId)?.abort();
}

export function removeConversation(id: string): void {
  // Its answer has nowhere to land once the conversation is gone.
  cancel(id);

  const conversations = { ...state.conversations };
  delete conversations[id];
  setState({
    conversations,
    order: state.order.filter((candidate) => candidate !== id),
  });
  void deleteStoredConversation(id);
}

/** Conversations in display order, newest first. */
export function conversationList(chatState: ChatState): Conversation[] {
  return chatState.order
    .map((id) => chatState.conversations[id])
    .filter((conversation) => conversation !== undefined);
}
