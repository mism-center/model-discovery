import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';

const SNIPPET_FIELD = /^[a-z_]+:/;
const TAXONOMY_RESOURCE = 'Taxonomy';

const HTML_TAG = /<[^>]*>/g;
const HTML_ENTITY = /&[a-z]+;|&#\d+;/gi;
const WHITESPACE = /\s+/g;
const ENTITIES: Record<string, string> = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&apos;': "'",
  '&#39;': "'",
  '&nbsp;': ' ',
};

/**
 * BioModels serves publication abstracts as XHTML, so a synopsis arrives with
 * `<h4>Background</h4>`-style markup embedded in it. Reduced to plain text
 * rather than rendered, because this is third-party markup and the card only
 * ever shows a few clamped lines of it.
 */
function plainText(value: string): string {
  return value
    .replaceAll(HTML_TAG, ' ')
    .replaceAll(HTML_ENTITY, (entity) => ENTITIES[entity.toLowerCase()] ?? ' ')
    .replaceAll(WHITESPACE, ' ')
    .trim();
}

/**
 * One field of CAIRNS' `snippet`, which is a serialised record rather than
 * prose: `name:` / `identifier:` / `description:`, one per line, and a value
 * may wrap onto following lines.
 */
function snippetField(snippet: string, field: string): string | undefined {
  const lines = snippet.split('\n');
  const start = lines.findIndex((line) => line.startsWith(`${field}:`));
  if (start === -1) return;

  const collected = [lines[start].slice(field.length + 1).trim()];
  for (let index = start + 1; index < lines.length; index++) {
    if (SNIPPET_FIELD.test(lines[index])) break;
    collected.push(lines[index].trim());
  }

  return collected.join(' ').trim() || undefined;
}

/**
 * The description repeats the record name verbatim on many BioModels entries,
 * which reads as a stutter directly under the title.
 */
function withoutLeadingName(
  description: string,
  name: string
): string | undefined {
  const trimmed = description.startsWith(name)
    ? description.slice(name.length).trim()
    : description;
  return trimmed || undefined;
}

export interface EvidenceFields {
  name: string;
  source: string;
  description?: string;
  accession?: string;
  url?: string;
  /** `CURATED` / `NON_CURATED`, absent for non-BioModels records. */
  curationStatus?: string;
  organisms: string[];
  publicationTitle?: string;
  publicationJournal?: string;
  modellingApproach?: string;
  format?: string;
}

/**
 * Everything a card can display, resolved once from the several places CAIRNS
 * and the BioModels enrichment scatter it across.
 *
 * `url` is empty on every card observed and `biomodels` is null for non-model
 * records, so the link is genuinely absent for some cards rather than derivable.
 */
/**
 * The publication synopsis is the paper's own abstract; the snippet
 * description is a truncated restatement of the record header, so it is only
 * a fallback.
 */
function describe(
  card: CairnsEvidenceCard,
  synopsis: string | undefined
): string | undefined {
  if (synopsis) return plainText(synopsis);

  const raw = snippetField(card.snippet ?? '', 'description');
  return raw ? withoutLeadingName(plainText(raw), card.name) : undefined;
}

export function evidenceFields(card: CairnsEvidenceCard): EvidenceFields {
  const bio = card.biomodels ?? undefined;

  return {
    name: card.name,
    source: card.source,
    description: describe(card, bio?.publication?.synopsis || undefined),
    // Only BioModels supplies a real accession; a tool's snippet `identifier`
    // is a slug that merely restates its name.
    accession: bio?.identifier || undefined,
    url: card.url || bio?.url || undefined,
    curationStatus: bio?.curation_status || undefined,
    organisms: (bio?.annotations ?? [])
      .filter((annotation) => annotation.resource === TAXONOMY_RESOURCE)
      .map((annotation) => annotation.name)
      .filter(Boolean),
    publicationTitle: bio?.publication?.title
      ? plainText(bio.publication.title)
      : undefined,
    publicationJournal: bio?.publication?.journal || undefined,
    modellingApproach: bio?.modelling_approach?.name || undefined,
    format: bio?.format?.name || undefined,
  };
}
