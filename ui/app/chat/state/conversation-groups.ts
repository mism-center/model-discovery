import type { Conversation } from './types';

const DAY_MS = 86_400_000;
const RECENT_DAYS = 6;

export interface ConversationGroup {
  label: string;
  conversations: Conversation[];
}

function startOfDay(timestamp: number): number {
  const date = new Date(timestamp);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

/**
 * The conversation's own first question. Nothing else in a stored conversation
 * describes it, and CAIRNS supplies no title.
 */
export function conversationTitle(conversation: Conversation): string {
  return conversation.turns[0]?.question ?? 'New conversation';
}

/**
 * Split conversations into date bands, preserving the order given. Empty bands
 * are dropped so a short history shows one heading rather than three.
 */
export function groupConversations(
  conversations: Conversation[],
  now: number
): ConversationGroup[] {
  const today = startOfDay(now);
  const recent = today - RECENT_DAYS * DAY_MS;

  const today_: Conversation[] = [];
  const week: Conversation[] = [];
  const older: Conversation[] = [];

  for (const conversation of conversations) {
    if (conversation.createdAt >= today) today_.push(conversation);
    else if (conversation.createdAt >= recent) week.push(conversation);
    else older.push(conversation);
  }

  return [
    { label: 'Today', conversations: today_ },
    { label: 'Previous 7 days', conversations: week },
    { label: 'Older', conversations: older },
  ].filter((group) => group.conversations.length > 0);
}
