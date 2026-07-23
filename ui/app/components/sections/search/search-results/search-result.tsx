import cn from 'classnames';
import { Button } from '@heroui/react';
import { BookmarkIcon } from '@heroicons/react/24/outline';
import {
  CalendarIcon,
  CircleStackIcon,
  UserIcon,
} from '@heroicons/react/16/solid';
import { DocumentIcon } from '@heroicons/react/24/solid';
import { QuotationMarkIcon } from '@sidekickicons/react/16/solid';
// import { Link } from 'react-router';

import type { SearchResultItem } from '~/api';
import { AuthorListTooltip } from './author-list-tooltip';
import { RunControls } from './run-controls';

/**
 * Format an ISO timestamp / date string as `Mon D, Year, H:MM AM/PM` (e.g. `Jan 22, 2024, 3:14 PM`).
 */
function formatDate(iso: string) {
  const date = new Date(iso);
  // Catch invalid dates
  if (Number.isNaN(date.valueOf())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

/**
 * Human-readable byte-size formatting.
 */
function formatSize(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

interface SearchResultProps {
  result: SearchResultItem;
}

export function SearchResult({ result }: SearchResultProps) {
  // Details-page navigation is disabled while the details route is unimplemented.
  // const isDataset = result.resource_type === 'dataset';
  // const linkPath = isDataset
  //   ? `/datasets/${result.id}/`
  //   : `/models/${result.id}/`;

  const formatTags = result.format_tags ?? [];
  const authors = result.authors ?? [];
  const publications = result.publications ?? [];
  const executable = Boolean(result.execution_type);

  // Prefer the dedicated publication date when available; fall back to the
  // row's created_at so we can at least render something otherwise.
  const displayDate = result.date_published ?? result.created_at;

  return (
    <div
      className={cn(
        'group relative p-6 rounded-2xl',
        'flex items-stretch justify-between gap-6',
        'transition-all duration-200',
        'bg-transparent hover:bg-primary/4',
        'hover:shadow-sm hover:shadow-primary/5 hover:-translate-y-px'
      )}
    >
      {/* Left content */}
      <div className="flex-1 min-w-0">
        {/* Executable badge (models only). Featured/starred isn't modeled by
            the API yet; if/when it is, add back here. */}
        {executable && (
          <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  'inline-flex items-center px-2 py-0.5',
                  'rounded-xs bg-primary',
                  'text-white text-[10px] font-bold uppercase tracking-wide'
                )}
              >
                Executable
              </span>
            </div>
          </div>
        )}

        {/* Title */}
        <h3
          className={cn(
            'relative w-fit text-xl font-bold font-headline text-primary',
            'after:absolute after:w-full after:h-0.5 after:-bottom-px after:left-0',
            'after:bg-primary after:content-[""]',
            'after:scale-x-0 after:origin-right after:transition-transform after:duration-150 after:ease-in-out',
            'group-hover:after:scale-x-100 group-hover:after:origin-left',
            'after:delay-0 group-hover:after:delay-150'
          )}
        >
          {result.name}
        </h3>

        {/* Description */}
        {result.description && (
          <p className="text-sm text-default-800 line-clamp-2 mt-2 leading-relaxed">
            {result.description}
          </p>
        )}

        {result.model_scales?.length || result.domains?.length ? (
          <div className="flex flex-wrap items-center gap-2 mt-3">
            {result.model_scales?.map((scale) => (
              <span
                key={scale}
                className={cn(
                  'px-2 py-0.5 rounded-xs text-[10px] font-bold uppercase tracking-tighter',
                  'bg-primary-100 text-primary/80'
                )}
              >
                {scale}
              </span>
            ))}
            {result.domains?.map((domain) => (
              <span
                key={domain}
                className={cn(
                  'px-2 py-0.5 rounded-xs text-[10px] font-bold uppercase tracking-tighter',
                  'bg-default-200 text-default-900/90'
                )}
              >
                {domain}
              </span>
            ))}
          </div>
        ) : null}

        {/* Metadata row */}
        <div className="flex items-center gap-4 mt-3 min-h-8">
          <div
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2',
              'text-[11px] text-default-800 uppercase tracking-tight'
            )}
          >
            {authors.length > 0 ? (
              <AuthorListTooltip authors={authors} />
            ) : (
              result.owner && (
                <div className="flex items-center gap-1.5 font-medium text-primary">
                  <UserIcon className="size-3.5" />
                  <span>{result.owner}</span>
                </div>
              )
            )}
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="size-3.5" />
              <span>{formatDate(displayDate)}</span>
            </div>
            {formatTags.length > 0 && (
              <div className="flex items-center gap-1.5">
                <DocumentIcon className="size-3.5" />
                <span className="uppercase tracking-wider">
                  {formatTags.join(' / ')}
                </span>
              </div>
            )}
            {typeof result.size_bytes === 'number' && (
              <div className="flex items-center gap-1.5">
                <CircleStackIcon className="size-3.5" />
                {formatSize(result.size_bytes)}
              </div>
            )}
            {publications.length > 0 && (
              <div className="flex items-center gap-1.5">
                <QuotationMarkIcon className="size-3.5 mb-1" />
                <span>
                  {publications.length}{' '}
                  {publications.length === 1 ? 'Publication' : 'Publications'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Right side actions */}
      <div className="flex flex-col justify-between items-end">
        <Button
          variant="flat"
          size="sm"
          isIconOnly
          className={cn(
            'bg-transparent rounded-lg hover:opacity-100! active:opacity-90!',
            'text-primary hover:bg-primary hover:text-white'
          )}
          onPress={() =>
            console.log('bookmark', result.resource_type, result.id)
          }
        >
          <BookmarkIcon className="size-5" />
        </Button>

        {/* View details — disabled until the details page is implemented.
            Replaced in this slot by <RunControls /> below.
        <Button
          size="sm"
          color="primary"
          className="px-5 py-2.5 rounded-lg text-sm font-bold"
        >
          View details
        </Button>
        */}
        {executable && <RunControls model={result} />}
      </div>
    </div>
  );
}
