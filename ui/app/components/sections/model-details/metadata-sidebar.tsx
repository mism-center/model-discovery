import { useState } from 'react';
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/16/solid';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { AuthorListTooltip } from '~/components/sections/search/search-results/author-list-tooltip';
import { formatBytes, formatMonthYear } from '~/utils/format';
import { Field } from './primitives';

/**
 * Sticky metadata sidebar: attribution, provenance, integrity, and lifecycle
 * status. Only fields with values render, so sparsely-annotated models don't
 * show a wall of em dashes.
 */
export function MetadataSidebar({ model }: { model: ModelDetailResponse }) {
  const publishedOrCreated = model.date_published ?? model.created_at;

  return (
    <aside className="lg:sticky lg:top-6 h-fit rounded-2xl border border-default-200 bg-default-50 p-6">
      <dl className="flex flex-col gap-4">
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
                  <span className="text-default-600">{k}:</span>
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
    </aside>
  );
}

function StatusPill({ value }: { value: string }) {
  if (!value) return null;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-default-200 text-[11px] font-semibold text-default-800 capitalize">
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
      className="inline-flex items-center gap-1.5 font-mono text-[12px] text-default-900 hover:text-primary"
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
