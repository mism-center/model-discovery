import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';

/**
 * Tool ids the answer cites.
 *
 * CAIRNS cites by embedding the evidence card's `tool_id` in brackets after the
 * record name (`**Wodarz2007 - HIV/CD4 T-cell interaction
 * [biomodels_biomd0000000663]**`) rather than with `[n]` markers. Matching each
 * known id against the text, instead of parsing citations out of it, means an
 * answer in any other shape simply cites nothing rather than mismatching.
 */
export function citedToolIds(
  answer: string,
  cards: CairnsEvidenceCard[]
): Set<string> {
  const cited = new Set<string>();
  for (const card of cards) {
    if (card.tool_id && answer.includes(`[${card.tool_id}]`)) {
      cited.add(card.tool_id);
    }
  }
  return cited;
}

/**
 * The card a single run of answer text cites, if any.
 *
 * Only bolded runs carrying a known id are citations; ordinary emphasis is not,
 * and must not be dressed as a link.
 */
export function citationToolId(
  text: string,
  cards: CairnsEvidenceCard[]
): string | undefined {
  for (const card of cards) {
    if (card.tool_id && text.includes(`[${card.tool_id}]`)) return card.tool_id;
  }
  return;
}

/**
 * Anchor for an evidence row. Scoped by turn because one thread renders an
 * evidence list per answer, and ids must stay unique across all of them.
 */
export function evidenceAnchorId(turnId: string, toolId: string): string {
  return `evidence-${turnId}-${toolId.replaceAll(/[^\w-]/g, '-')}`;
}
