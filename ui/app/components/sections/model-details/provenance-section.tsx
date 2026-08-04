import { useState } from 'react';
import cn from 'classnames';
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/16/solid';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { formatBytes } from '~/utils/format';
import {
  Field,
  LINK,
  SectionAbsence,
  SectionCard,
  hasItems,
} from './primitives';

/**
 * Identifiers and integrity — what's left of provenance once the questions a
 * reader asks up front (authors, citation, license, version, date) move into the
 * title byline. See `model-byline.tsx`.
 *
 * Does not show `status` / `registration_status`. Every catalogued model reads
 * "active"/"approved", so the pills cost a field and answered nothing.
 *
 * Styled like every other section — a rule, a heading, fields. Sitting last on
 * the page is the de-emphasis; it needs no container of its own, and giving it
 * one made it the only boxed group on a deliberately flat page.
 *
 * Two grids on purpose. Grid rows size to their tallest cell, so mixing one-line
 * scalars with multi-line lists in a single grid left large voids beside the
 * short fields.
 */
export function ProvenanceSection({ model }: { model: ModelDetailResponse }) {
  // The byline already cites the primary publication; listing a lone publication
  // again here would just repeat it. More than one and the full list earns its
  // place.
  const showPublications = (model.publications?.length ?? 0) > 1;

  const hasScalars =
    Boolean(model.contact_email) ||
    typeof model.size_bytes === 'number' ||
    Boolean(model.digest_sha256);

  const hasLongForm =
    hasItems(model.contacts) ||
    hasItems(model.related_resources) ||
    hasItems(model.funding) ||
    showPublications ||
    Boolean(model.external_ids && Object.keys(model.external_ids).length > 0);

  return (
    <SectionCard title="Provenance" description="Identifiers and integrity.">
      {hasScalars || hasLongForm ? (
        <>
          {hasScalars && (
            <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {model.contact_email && (
                <Field label="Contact">
                  <a href={`mailto:${model.contact_email}`} className={LINK}>
                    {model.contact_email}
                  </a>
                </Field>
              )}

              {typeof model.size_bytes === 'number' && (
                <Field label="Size">{formatBytes(model.size_bytes)}</Field>
              )}

              {model.digest_sha256 && (
                <Field label="SHA-256">
                  <ChecksumValue value={model.digest_sha256} />
                </Field>
              )}
            </dl>
          )}

          {hasLongForm && (
            <dl
              className={cn('grid gap-6 sm:grid-cols-2', hasScalars && 'mt-8')}
            >
              {hasItems(model.contacts) && (
                <Field label="Contacts">
                  <ul className="flex flex-col gap-1.5">
                    {model.contacts.map((c) => (
                      <li key={`${c.name}-${c.email}`}>
                        <span className="font-semibold">{c.name}</span>
                        {c.role && (
                          <span className="text-default-800"> · {c.role}</span>
                        )}
                        {c.email && (
                          <>
                            {' '}
                            <a href={`mailto:${c.email}`} className={LINK}>
                              {c.email}
                            </a>
                          </>
                        )}
                        {c.affiliation && (
                          <div className="text-default-800">
                            {c.affiliation}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </Field>
              )}

              {showPublications && hasItems(model.publications) && (
                <Field label="Publications">
                  <ul className="flex flex-col gap-2">
                    {model.publications.map((p, i) => {
                      const href =
                        p.url ||
                        (p.doi ? `https://doi.org/${p.doi}` : undefined);
                      return (
                        <li key={p.doi || p.title || i}>
                          {href ? (
                            <a
                              href={href}
                              target="_blank"
                              rel="noreferrer"
                              className={LINK}
                            >
                              {p.title || href}
                            </a>
                          ) : (
                            <span>{p.title}</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </Field>
              )}

              {/*
               * The registry's only provenance link — `qualifier` carries the
               * relationship (bqmodel:isDerivedFrom, bqbiol:isVersionOf, …),
               * which is the only thing on the page answering "where did this
               * come from".
               */}
              {hasItems(model.related_resources) && (
                <Field label="Related">
                  <ul className="flex flex-col gap-1.5">
                    {model.related_resources.map((r) => (
                      <li key={`${r.qualifier}-${r.scheme}-${r.value}`}>
                        <span className="font-semibold">
                          {formatQualifier(r.qualifier)}
                        </span>
                        <div className="font-mono text-xs text-default-900">
                          {[r.scheme, r.value].filter(Boolean).join(':')}
                        </div>
                      </li>
                    ))}
                  </ul>
                </Field>
              )}

              {model.external_ids &&
                Object.keys(model.external_ids).length > 0 && (
                  <Field label="External IDs">
                    <ul className="flex flex-col gap-1">
                      {Object.entries(model.external_ids).map(([k, v]) => (
                        <li key={k} className="flex gap-1.5">
                          <span className="text-default-800">{k}:</span>
                          <span>{v}</span>
                        </li>
                      ))}
                    </ul>
                  </Field>
                )}

              {hasItems(model.funding) && (
                <Field label="Funding">{model.funding.join(', ')}</Field>
              )}
            </dl>
          )}
        </>
      ) : (
        <SectionAbsence>
          No registry identifiers or integrity data have been recorded for this
          model.
        </SectionAbsence>
      )}
    </SectionCard>
  );
}

/**
 * Turn a CURIE-style relationship qualifier into something readable:
 * `bqmodel:isDerivedFrom` → `Is derived from`.
 */
function formatQualifier(qualifier: string): string {
  const local = qualifier.includes(':')
    ? qualifier.slice(qualifier.indexOf(':') + 1)
    : qualifier;
  const spaced = local.replaceAll(/([a-z0-9])([A-Z])/g, '$1 $2').toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function ChecksumValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const short = `${value.slice(0, 12)}…`;

  const copy = () => {
    void navigator.clipboard?.writeText(value).then(() => {
      setCopied(true);
      globalThis.setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <button
      type="button"
      onClick={copy}
      title={value}
      className="inline-flex items-center gap-1.5 font-mono text-xs text-default-900 hover:text-primary"
    >
      {short}
      {copied ? (
        <CheckIcon className="size-3.5 text-success-600" />
      ) : (
        <ClipboardDocumentIcon className="size-3.5" />
      )}
    </button>
  );
}
