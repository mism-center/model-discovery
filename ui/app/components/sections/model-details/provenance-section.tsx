import { useState } from 'react';
import cn from 'classnames';
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/16/solid';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { formatMonthYear, formatBytes } from '~/utils/format';
import {
  Field,
  LINK,
  SectionAbsence,
  SectionCard,
  hasItems,
  hasValue,
} from './primitives';

/**
 * Identifiers and integrity — what's left of provenance once the questions a
 * reader asks up front (authors, citation, license, version, date) move into the
 * title byline. See `model-byline.tsx`.
 *
 * Does not show bare `status` / `registration_status` as a pill — every
 * *catalogued* (publicly visible) model reads "active"/"approved", so the pill
 * would cost a field and answer nothing. It does show the metadata review
 * decision below, once there is one to show: a rejection reason is exactly the
 * kind of information the pill's absence-of-variance argument does not cover,
 * since only the model's owner (or a reviewer) ever sees a non-approved model
 * at all.
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

  // Gated on `registration_status` itself, not just on `metadata_reviewed_by`
  // being set: after a rejected package is resubmitted, status bounces back to
  // `pending_review` while `metadata_reviewed_by`/`_at` are left as history of
  // the *previous* decision (see the backend's resubmit convention) — showing
  // "Approved"/"Rejected" while a fresh review is pending would misrepresent an
  // old verdict as the current one. Pre-MISM-291 resources have an empty
  // `metadata_reviewed_by`, so `hasValue` alone already excludes them.
  const hasMetadataReview =
    (model.registration_status === 'approved' ||
      model.registration_status === 'rejected') &&
    hasValue(model.metadata_reviewed_by);

  const hasScalars =
    Boolean(model.contact_email) ||
    typeof model.size_bytes === 'number' ||
    Boolean(model.digest_sha256) ||
    hasMetadataReview;

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

              {hasMetadataReview && (
                <Field label="Metadata review">
                  <MetadataReviewValue model={model} />
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
 * The UPLOAD_REVIEWER's decision on this model's metadata package (MISM-291).
 * Only rendered by the caller once `registration_status` is `approved` or
 * `rejected` with a real `metadata_reviewed_by` — see `hasMetadataReview`'s
 * comment above for why the gate checks status rather than reviewer presence.
 */
function MetadataReviewValue({ model }: { model: ModelDetailResponse }) {
  const rejected = model.registration_status === 'rejected';
  return (
    <>
      <span className={cn('font-semibold', rejected && 'text-danger-600')}>
        {rejected ? 'Rejected' : 'Approved'}
      </span>
      <span className="text-default-800">
        {' '}
        · {model.metadata_reviewed_by}
        {model.metadata_reviewed_at &&
          ` · ${formatMonthYear(model.metadata_reviewed_at)}`}
      </span>
      {rejected && hasValue(model.metadata_rejection_reason) && (
        <div className="mt-1 text-default-800">
          {model.metadata_rejection_reason}
        </div>
      )}
    </>
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
