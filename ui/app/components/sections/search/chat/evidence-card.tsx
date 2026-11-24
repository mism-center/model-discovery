import { ArrowTopRightOnSquareIcon } from '@heroicons/react/16/solid';
import { QuotationMarkIcon } from '@sidekickicons/react/16/solid';
import cn from 'classnames';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';
import { evidenceFields } from '~/chat/state/evidence-fields';
import { ACTION_LINK, EvidenceImportAction } from './evidence-import-action';

const TAG =
  'px-2 py-0.5 rounded-xs text-[10px] font-bold uppercase tracking-tighter';

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
    { label: 'Category', values: fields.categories },
    { label: 'Topics', values: fields.topics },
    { label: 'Language', values: fields.languages },
  ].filter((attribute) => attribute.values.length > 0);

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
            <span className={cn(TAG, 'bg-secondary text-white')}>
              {fields.sourceLabel}
            </span>
            {/* {fields.accession ? (
              <span className={cn(TAG, 'bg-default-200 text-default-900/90')}>
                {fields.accession}
              </span>
            ) : undefined} */}
          </div>

          <h3 className="font-headline text-xl font-bold text-primary">
            {fields.name}
          </h3>

          {fields.description ? (
            <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-default-800">
              {fields.description}
            </p>
          ) : undefined}

          {fields.citation ? (
            <div className="mt-3 flex items-start gap-1.5 text-[11px] uppercase tracking-tight text-default-800">
              <QuotationMarkIcon className="size-3.5 shrink-0" />
              <span>{fields.citation}</span>
            </div>
          ) : undefined}
        </div>

        <div className="flex shrink-0 flex-col gap-5 border-default-200 lg:w-[246px] lg:border-l lg:pl-6">
          {attributes.map((attribute) => (
            <Attribute
              key={attribute.label}
              label={attribute.label}
              value={attribute.values.join(', ')}
            />
          ))}
          <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {fields.url ? (
              <a
                className={ACTION_LINK}
                href={fields.url}
                rel="noreferrer noopener"
                target="_blank"
              >
                View details
                <ArrowTopRightOnSquareIcon className="size-3.5" />
              </a>
            ) : undefined}
            {fields.url || card.mism_model_id ? undefined : (
              <span className="text-xs text-default-800">
                No link available
              </span>
            )}
            <EvidenceImportAction card={card} />
          </div>
        </div>
      </div>
    </li>
  );
}
