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
