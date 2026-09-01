import { useMemo, useState } from 'react';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';
import { citedToolIds, evidenceAnchorId } from '~/chat/state/citations';
import { EvidenceCard } from './evidence-card';

export function EvidenceList({
  cards,
  answer,
  turnId,
}: {
  cards: CairnsEvidenceCard[];
  answer: string;
  turnId: string;
}) {
  const cited = useMemo(() => citedToolIds(answer, cards), [answer, cards]);
  const [showAll, setShowAll] = useState(false);

  if (cards.length === 0) return;

  // With nothing matched, the answer cites in a shape this does not recognise;
  // filtering on it would hide every card rather than the uncited ones.
  const canFilter = cited.size > 0 && cited.size < cards.length;
  const visible =
    canFilter && !showAll
      ? cards.filter((card) => cited.has(card.tool_id))
      : cards;

  return (
    <section className="mt-6">
      <div className="mb-1 flex items-baseline justify-between gap-4">
        <h3 className="text-[10px] font-bold uppercase tracking-wide text-default-800">
          Evidence ({visible.length}
          {canFilter && !showAll ? ` of ${cards.length}` : ''})
        </h3>
        {canFilter ? (
          <button
            className="text-xs text-secondary underline underline-offset-2 hover:text-primary"
            onClick={() => setShowAll((previous) => !previous)}
            type="button"
          >
            {showAll ? 'Show cited only' : `Show all ${cards.length} retrieved`}
          </button>
        ) : undefined}
      </div>
      <ul>
        {visible.map((card) => (
          <EvidenceCard
            anchorId={evidenceAnchorId(turnId, card.tool_id)}
            card={card}
            key={card.tool_id}
          />
        ))}
      </ul>
    </section>
  );
}
