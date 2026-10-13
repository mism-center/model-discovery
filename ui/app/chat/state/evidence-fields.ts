import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';

/** CAIRNS' source for records held in an MDSC registry. */
const MISM_SOURCE = 'MISM_models';

const SOURCE_LABELS: Record<string, string> = { [MISM_SOURCE]: 'MISM' };

const HTML_ENTITY = /&[a-z]+;|&#\d+;/gi;
const ENTITIES: Record<string, string> = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&apos;': "'",
  '&#39;': "'",
  '&nbsp;': ' ',
};

/** BioModels descriptions reach CAIRNS as XHTML, and keep their entities. */
function decodeEntities(value: string | undefined): string | undefined {
  return (
    value
      ?.replaceAll(
        HTML_ENTITY,
        (entity) => ENTITIES[entity.toLowerCase()] ?? ' '
      )
      .trim() || undefined
  );
}

export interface EvidenceFields {
  name: string;
  sourceLabel: string;
  description?: string;
  /**
   * The record's page at its source. Never set for a MISM record: its page is
   * in this registry, which `mism_model_id` links to.
   */
  url?: string;
  citation?: string;
  categories: string[];
  topics: string[];
  languages: string[];
}

/**
 * Everything a card displays, read from CAIRNS' schema.org record, which every
 * source is normalized into. `metadata` is absent on conversations saved before
 * CAIRNS returned it.
 */
export function evidenceFields(card: CairnsEvidenceCard): EvidenceFields {
  const { metadata } = card;

  return {
    name: card.name,
    sourceLabel: SOURCE_LABELS[card.source] ?? card.source,
    description: decodeEntities(metadata?.description),
    url:
      card.source === MISM_SOURCE
        ? undefined
        : card.url || metadata?.url || undefined,
    citation: metadata?.citation?.[0]?.name || undefined,
    categories: metadata?.application_category ?? [],
    topics: (metadata?.topic_category ?? [])
      .map((term) => term.name ?? '')
      .filter(Boolean),
    languages: metadata?.programming_language ?? [],
  };
}
