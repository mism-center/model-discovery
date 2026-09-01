import { useMemo, useState } from 'react';
import { ArrowTopRightOnSquareIcon } from '@heroicons/react/16/solid';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';
import { citedToolIds, evidenceAnchorId } from '~/chat/state/citations';

/**
 * Provisional evidence rendering. The designed record card replaces this.
 */

/**
 * CAIRNS returns `url` empty on every card observed, so the usable link comes
 * from BioModels enrichment. That enrichment is allowed to fail silently
 * (`api/v1/cairns.py`), leaving nothing to link to.
 */
function evidenceUrl(card: CairnsEvidenceCard): string | undefined {
  return card.url || card.biomodels?.url || undefined;
}

function EvidenceRow({
  card,
  turnId,
}: {
  card: CairnsEvidenceCard;
  turnId: string;
}) {
  const href = evidenceUrl(card);

  return (
    <li
      className="flex scroll-mt-20 items-baseline gap-3 border-b border-default-100 px-2 py-2 target:animate-evidence-target last:border-b-0"
      id={evidenceAnchorId(turnId, card.tool_id)}
    >
      <span className="shrink-0 rounded-xs bg-default-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-default-800">
        {card.source}
      </span>
      <span className="min-w-0 flex-1 text-sm text-default-900">
        {card.name}
      </span>
      {href ? (
        <a
          className="inline-flex shrink-0 items-center gap-1 text-xs text-secondary underline underline-offset-2 hover:text-primary"
          href={href}
          rel="noreferrer noopener"
          target="_blank"
        >
          Open
          <ArrowTopRightOnSquareIcon className="size-3" />
        </a>
      ) : undefined}
    </li>
  );
}

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
          <EvidenceRow card={card} key={card.tool_id} turnId={turnId} />
        ))}
      </ul>
    </section>
  );
}
