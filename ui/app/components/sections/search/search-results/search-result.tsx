import { parseDate } from '@internationalized/date';
import type {
  DatasetResult,
  ModelResult,
  ResultType,
} from '~/api/services/search';
import cn from 'classnames';
import { Button } from '@heroui/react';
import { QuotationMarkIcon } from '@sidekickicons/react/16/solid';
import { BookmarkIcon } from '@heroicons/react/24/outline';
import { AuthorListTooltip } from './author-list-tooltip';
import { CalendarIcon, CircleStackIcon, StarIcon, TagIcon } from '@heroicons/react/16/solid';
import { Link } from 'react-router';
import { DocumentIcon } from '@heroicons/react/24/solid';

// `Mon Year`
function formatDate(dateString: string) {
  const date = parseDate(dateString);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    year: 'numeric',
  }).format(date.toDate('UTC'));
}

function formatSize(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

interface SearchResultProps {
  result: ModelResult | DatasetResult;
  resultType: ResultType;
}

export function SearchResult({ result, resultType }: SearchResultProps) {
  const doi = resultType === 'models' ? (result as ModelResult).doi : undefined;
  const executable =
    resultType === 'models' ? (result as ModelResult).executable : false;
  const types =
    resultType === 'models' ? (result as ModelResult).types : undefined;
  const sizeBytes =
    resultType === 'datasets'
      ? (result as DatasetResult).size_bytes
      : undefined;
  const formats = resultType === 'datasets' ? (result as DatasetResult).formats : undefined

  const linkPath =
    resultType === 'models'
      ? `/models/${result.id}/`
      : `/datasets/${result.id}/`;

  return (
    <Link
      to={linkPath}
      className={cn(
        'group relative p-6 rounded-2xl',
        'flex items-stretch justify-between gap-6',
        'transition-all duration-200',
        'bg-transparent hover:bg-primary/4',
        'hover:shadow-sm hover:shadow-primary/5 hover:-translate-y-px',
        'active:scale-[0.995]'
      )}
    >
      {/* Left content */}
      <div className="flex-1 min-w-0">
        {/* Featured / executable badges */}
        {/* min-h-8 to align with bookmark button when badges are present */}
        {(result.featured || executable) && (
          <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
            <div className="flex flex-wrap items-center gap-2">
              {result.featured && (
                <span
                  className={cn(
                    'inline-flex items-center px-2 py-0.5',
                    'rounded-xs bg-success',
                    'text-black text-[10px] font-bold uppercase tracking-wide'
                  )}
                >
                  <StarIcon className="size-3 mr-1" />
                  Featured {resultType === 'models' ? 'Model' : 'Dataset'}
                </span>
              )}
              {executable && (
                <span
                  className={cn(
                    'inline-flex items-center px-2 py-0.5',
                    'rounded-xs bg-primary',
                    'text-white text-[10px] font-bold uppercase tracking-wide'
                  )}
                >
                  Executable
                </span>
              )}
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
            'after:delay-0 group-hover:after:delay-150',
          )}
        >
          {result.title}
        </h3>

        {/* Description */}
        <p className="text-sm text-default-800 line-clamp-2 mt-2 leading-relaxed">
          {result.description}
        </p>

        <div className="flex flex-wrap items-center gap-2 mt-3">
          {result.scales.map((scale) => (
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
          {types?.map((type) => (
            <span
              key={type}
              className={cn(
                'px-2 py-0.5 rounded-xs text-[10px] font-bold uppercase tracking-tighter',
                'bg-default-200 text-default-900/90'
              )}
            >
              {type}
            </span>
          ))}
        </div>

        {/* Metadata and actions */}
        {/* min-h-8 to align text with details button */}
        <div className="flex items-center gap-4 mt-3 min-h-8">
          <div
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2',
              'text-[11px] text-default-800 uppercase tracking-tight'
            )}
          >
            <AuthorListTooltip result={result} />
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="size-3.5" />
              <span>{formatDate(result.published_date)}</span>
            </div>
            {doi !== undefined && (
              <div className="flex items-center gap-1.5">
                <TagIcon className="size-3.5" />
                <span className="uppercase tracking-wider">DOI: {doi}</span>
              </div>
            )}
            {formats?.length && (
              <div className="flex items-center gap-1.5">
                <DocumentIcon className="size-3.5" />
                <span className="uppercase tracking-wider">
                  {formats.join(' / ')}
                </span>
              </div>
            )}
            {sizeBytes !== undefined && (
              <div className="flex items-center gap-1.5">
                <CircleStackIcon className="size-3.5" />
                {formatSize(sizeBytes)}
              </div>
            )}
            {result.citations !== undefined && (
              <div className="flex items-center gap-1.5">
                <QuotationMarkIcon className="size-3.5 mb-1" />
                <span>{result.citations} Citations</span>
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
          onClick={(e) => e.preventDefault()}
          onPress={() =>
            console.log('bookmark', resultType.slice(0, -1), result.id)
          }
        >
          <BookmarkIcon className="size-5" />
        </Button>

        <Button
          size="sm"
          color="primary"
          className="px-5 py-2.5 rounded-lg text-sm font-bold"
          // Doesn't actually need an onPress since the entire card functions as a link
        >
          View details
        </Button>
      </div>
    </Link>
  );
}
