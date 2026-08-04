import { useState } from 'react';
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/16/solid';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { AuthorListTooltip } from '~/components/sections/search/search-results/author-list-tooltip';
import { formatBytes, formatMonthYear } from '~/utils/format';
import { Field, SectionCard } from './primitives';

/**
 * Attribution, provenance, integrity and lifecycle.
 *
 * Was a sticky right-hand rail styled `bg-default-50` on a `bg-default-50` page
 * — separated from its surroundings by a border measuring 1.14:1, so it read as
 * unstyled floating text next to white cards. It is now a normal section in the
 * content pane, which also stops publications (primary scholarly content) from
 * being buried in a 320px gutter, and lays the fields out in a grid rather than
 * a single 14-item column.
 */
export function MetadataSidebar({ model }: { model: ModelDetailResponse }) {
  const publishedOrCreated = model.date_published ?? model.created_at;

  return (
    <SectionCard
      title="Provenance"
      description="Attribution, publications, licensing and integrity."
    >
      <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Status">
          <div className="flex flex-wrap gap-1.5">
            <StatusPill value={model.status} />
            <StatusPill value={model.registration_status} />
          </div>
        </Field>

        {model.version && <Field label="Version">{model.version}</Field>}

        {model.authors && model.authors.length > 0 ? (
          <Field label="Authors">
            <AuthorListTooltip authors={model.authors} />
          </Field>
        ) : (
          model.owner && <Field label="Owner">{model.owner}</Field>
        )}

        {model.organization && (
          <Field label="Organization">{model.organization}</Field>
        )}

        {model.contact_email && (
          <Field label="Contact">
            <a
              href={`mailto:${model.contact_email}`}
              className="text-secondary hover:underline"
            >
              {model.contact_email}
            </a>
          </Field>
        )}

        {model.contacts && model.contacts.length > 0 && (
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
                      <a
                        href={`mailto:${c.email}`}
                        className="text-secondary-700 hover:underline"
                      >
                        {c.email}
                      </a>
                    </>
                  )}
                  {c.affiliation && (
                    <div className="text-default-800">{c.affiliation}</div>
                  )}
                </li>
              ))}
            </ul>
          </Field>
        )}

        {/*
         * The registry's only provenance link — `qualifier` carries the
         * relationship (bqmodel:isDerivedFrom, bqbiol:isVersionOf, …). Rendered
         * because it answers "where did this model come from", which nothing
         * else on the page could.
         */}
        {model.related_resources && model.related_resources.length > 0 && (
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

        {model.organisms && model.organisms.length > 0 && (
          <Field label="Organisms">{model.organisms.join(', ')}</Field>
        )}

        {model.funding && model.funding.length > 0 && (
          <Field label="Funding">{model.funding.join(', ')}</Field>
        )}

        {model.license && <Field label="License">{model.license}</Field>}

        {model.publications && model.publications.length > 0 && (
          <Field label="Publications">
            <ul className="flex flex-col gap-2">
              {model.publications.map((p, i) => {
                const href =
                  p.url || (p.doi ? `https://doi.org/${p.doi}` : undefined);
                return (
                  <li key={p.doi || p.title || i}>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noreferrer"
                        className="text-secondary hover:underline"
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

        {model.external_ids && Object.keys(model.external_ids).length > 0 && (
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

        {typeof model.size_bytes === 'number' && (
          <Field label="Size">{formatBytes(model.size_bytes)}</Field>
        )}

        <Field label="Published">{formatMonthYear(publishedOrCreated)}</Field>

        {model.digest_sha256 && (
          <Field label="SHA-256">
            <ChecksumValue value={model.digest_sha256} />
          </Field>
        )}
      </dl>
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

function StatusPill({ value }: { value: string }) {
  if (!value) return null;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-default-200 text-xs font-semibold text-default-800 capitalize">
      {value.replaceAll('_', ' ')}
    </span>
  );
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
