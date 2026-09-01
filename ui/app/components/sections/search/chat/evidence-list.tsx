import { ArrowTopRightOnSquareIcon } from '@heroicons/react/16/solid';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';

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

function EvidenceRow({ card }: { card: CairnsEvidenceCard }) {
  const href = evidenceUrl(card);

  return (
    <li className="flex items-baseline gap-3 border-b border-default-100 py-2 last:border-b-0">
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

export function EvidenceList({ cards }: { cards: CairnsEvidenceCard[] }) {
  if (cards.length === 0) return;

  return (
    <section className="mt-6">
      <h3 className="mb-1 text-[10px] font-bold uppercase tracking-wide text-default-800">
        Evidence ({cards.length})
      </h3>
      <ul>
        {cards.map((card) => (
          <EvidenceRow card={card} key={card.tool_id} />
        ))}
      </ul>
    </section>
  );
}
