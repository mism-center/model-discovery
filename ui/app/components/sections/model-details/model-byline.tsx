import { Fragment } from 'react';
import { DocumentTextIcon } from '@heroicons/react/16/solid';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { AuthorListTooltip } from '~/components/sections/search/search-results/author-list-tooltip';
import { formatMonthYear } from '~/utils/format';
import { LINK, hasItems } from './primitives';

type Publication = NonNullable<ModelDetailResponse['publications']>[number];

/** `2.1` → `v2.1`, but leave an already-prefixed `v2.1` alone. */
function formatVersion(version: string): string {
  const trimmed = version.trim();
  return /^v/i.test(trimmed) ? trimmed : `v${trimmed}`;
}

function publicationHref(publication: Publication): string | undefined {
  return (
    publication.url ||
    (publication.doi ? `https://doi.org/${publication.doi}` : undefined)
  );
}

/** The publication a reader should cite: the first one that can be identified. */
function primaryPublication(
  publications: ModelDetailResponse['publications']
): Publication | undefined {
  if (!hasItems(publications)) return undefined;
  return publications.find((p) => p.title || publicationHref(p));
}

/**
 * Attribution, licensing and citation, directly under the title.
 *
 * These were originally in the Provenance section at the foot of the page, on
 * the reasoning that provenance is reference material. That over-generalized: a
 * checksum is reference material, but "who wrote this, what paper is it from,
 * may I use it" are questions asked *before* deciding to keep reading, and every
 * comparable registry (Zenodo, BioModels, Hugging Face) surfaces them at the top
 * while burying only the technical residue.
 *
 * Facts are unlabeled and `·`-separated — the byline convention. Each one is
 * self-identifying (an SPDX id, a `v`-prefixed version, a month and year), so
 * labels would cost more than they explain.
 */
export function ModelByline({ model }: { model: ModelDetailResponse }) {
  const facts: Array<{ key: string; node: React.ReactNode }> = [];

  if (hasItems(model.authors)) {
    facts.push({
      key: 'authors',
      node: <AuthorListTooltip authors={model.authors} />,
    });
  } else if (model.owner) {
    facts.push({ key: 'owner', node: model.owner });
  }

  if (model.organization) {
    facts.push({ key: 'organization', node: model.organization });
  }
  if (model.version) {
    facts.push({ key: 'version', node: formatVersion(model.version) });
  }
  if (model.license) {
    facts.push({ key: 'license', node: model.license });
  }

  const published = model.date_published ?? model.created_at;
  if (published) {
    facts.push({ key: 'published', node: formatMonthYear(published) });
  }

  const citation = primaryPublication(model.publications);

  if (facts.length === 0 && !citation) return null;

  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {facts.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-default-800">
          {facts.map((fact, i) => (
            <Fragment key={fact.key}>
              {i > 0 && (
                <span aria-hidden="true" className="text-default-700">
                  ·
                </span>
              )}
              {fact.node}
            </Fragment>
          ))}
        </div>
      )}
      {citation && <Citation publication={citation} />}
    </div>
  );
}

function Citation({ publication }: { publication: Publication }) {
  const href = publicationHref(publication);
  const label = publication.title || href;

  return (
    <p className="flex items-start gap-1.5 text-sm">
      <DocumentTextIcon
        aria-hidden="true"
        className="size-4 shrink-0 mt-0.5 text-default-800"
      />
      {/* The icon is decorative, so the link would otherwise announce a bare
          title with no indication of what it is. */}
      <span className="sr-only">Citation: </span>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className={LINK}>
          {label}
        </a>
      ) : (
        <span className="text-default-900">{label}</span>
      )}
    </p>
  );
}
