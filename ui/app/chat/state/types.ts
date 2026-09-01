import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';

/**
 * `pending` is the only generating state, and it lives on the turn rather than
 * beside the store. A conversation is generating iff one of its own turns is
 * pending, so one conversation's request can never gate or scroll another.
 */
export type TurnStatus = 'pending' | 'answered' | 'failed' | 'cancelled';

export interface ChatTurn {
  id: string;
  question: string;
  askedAt: number;
  status: TurnStatus;
  answer?: string;
  evidence?: CairnsEvidenceCard[];
  /** As reported by CAIRNS, not measured client-side. */
  elapsedSeconds?: number;
  error?: string;
}

export interface Conversation {
  id: string;
  createdAt: number;
  turns: ChatTurn[];
}

export interface ChatState {
  conversations: Record<string, Conversation>;
  /** Conversation ids, most recently created first. */
  order: string[];
}
