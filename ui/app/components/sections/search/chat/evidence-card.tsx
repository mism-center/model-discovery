import { ArrowTopRightOnSquareIcon } from '@heroicons/react/16/solid';
import { QuotationMarkIcon } from '@sidekickicons/react/16/solid';
import { Button } from '@heroui/react';
import cn from 'classnames';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';
import {
  type EvidenceFields,
  evidenceFields,
} from '~/chat/state/evidence-fields';

const TAG =
  'px-2 py-0.5 rounded-xs text-[10px] font-bold uppercase tracking-tighter';

/**
 * Curation is a property of the record's presence in BioModels, so it reads as
 * a qualifier on the source rather than a badge competing with it.
 */
function sourceLabel(fields: EvidenceFields): string {
  if (fields.curationStatus === 'CURATED') return `${fields.source} (curated)`;
  return fields.source;
}

function Attribute({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-tight text-default-800">
        {label}
      </div>
      <div className="mt-1 text-xs leading-5 text-default-900">{value}</div>
    </div>
  );
}

export function EvidenceCard({
  card,
  anchorId,
}: {
  card: CairnsEvidenceCard;
  anchorId: string;
}) {
  const fields = evidenceFields(card);

  const attributes = [
    fields.organisms.length > 0
      ? { label: 'Organism', value: fields.organisms.join(', ') }
      : undefined,
    fields.modellingApproach
      ? { label: 'Approach', value: fields.modellingApproach }
      : undefined,
    fields.format ? { label: 'Format', value: fields.format } : undefined,
  ].filter((entry) => entry !== undefined);

  return (
    <li
      className={cn(
        'scroll-mt-20 target:animate-evidence-target',
        'group rounded-2xl p-6 transition-all duration-200',
        'bg-transparent hover:bg-primary/4',
        'hover:shadow-sm hover:shadow-primary/5 hover:-translate-y-px'
      )}
      id={anchorId}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-stretch lg:justify-between lg:gap-6">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex min-h-8 flex-wrap items-center gap-2">
            <span className={cn(TAG, 'bg-primary-100 text-primary/80')}>
              {sourceLabel(fields)}
            </span>
            {fields.accession ? (
              <span className={cn(TAG, 'bg-default-200 text-default-900/90')}>
                {fields.accession}
              </span>
            ) : undefined}
          </div>

          <h3 className="font-headline text-xl font-bold text-primary">
            {fields.name}
          </h3>

          {fields.description ? (
            <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-default-800">
              {fields.description}
            </p>
          ) : undefined}

          {fields.publicationTitle ? (
            <div className="mt-3 flex items-start gap-1.5 text-[11px] uppercase tracking-tight text-default-800">
              <QuotationMarkIcon className="size-3.5 shrink-0" />
              <span>
                {fields.publicationTitle}
                {fields.publicationJournal ? (
                  <span className="text-default-800/80">
                    {' '}
                    · {fields.publicationJournal}
                  </span>
                ) : undefined}
              </span>
            </div>
          ) : undefined}
        </div>

        <div className="flex shrink-0 flex-col gap-5 border-default-200 lg:w-[246px] lg:border-l lg:pl-6">
          {attributes.map((attribute) => (
            <Attribute
              key={attribute.label}
              label={attribute.label}
              value={attribute.value}
            />
          ))}
          <div className="mt-auto">
            {fields.url ? (
              <Button
                as="a"
                className="text-primary"
                endContent={<ArrowTopRightOnSquareIcon className="size-3.5" />}
                href={fields.url}
                rel="noreferrer noopener"
                size="sm"
                target="_blank"
                variant="flat"
              >
                View details
              </Button>
            ) : (
              <span className="text-xs text-default-800">
                No link available
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
