import type { ReactNode } from 'react';
import cn from 'classnames';
import { Link } from 'react-router';
import { CalendarIcon, UserIcon } from '@heroicons/react/16/solid';

import type { SearchResultItem } from '~/api';
import type { ModelListItem } from '~/api/endpoints/models';
import { formatDateTime } from '~/utils/format';
import { AuthorListTooltip } from '~/components/sections/search/search-results/author-list-tooltip';

interface ReviewCardProps {
  /** Text shown in the warning badge above the title. */
  badge: string;
  /** Accepts both search result items and models-list items — the fields
   *  used here exist on both. */
  model: ModelListItem | SearchResultItem;
  /**
   * How the title is rendered:
   * - `'link'`    — `<Link>` to the model detail page (reviewer cards)
   * - `'heading'` — `<h3>` with animated underline on group-hover (owner cards)
   *
   * Defaults to `'heading'`.
   */
  titleAs?: 'link' | 'heading';
  /** Optional content rendered directly below the title (e.g. container info or description). */
  subtitle?: ReactNode;
  /**
   * When `true`, the metadata row shows `AuthorListTooltip` (or falls back to
   * the owner field). When `false` (default), only the owner field is shown.
   */
  showAuthors?: boolean;
  /**
   * Optional error node rendered after the metadata row (no wrapper added —
   * the caller is responsible for styling, e.g. `<ApiErrorDisplay className="mt-3" />`).
   */
  error?: ReactNode;
  /**
   * The full right-column content: action buttons and any portalled modals.
   * `ReviewCard` provides the column wrapper (`flex flex-col justify-between
   * items-end gap-2`) so callers only need to supply the buttons and modals.
   */
  actions: ReactNode;
}

export function ReviewCard({
  badge,
  model,
  titleAs = 'heading',
  subtitle,
  showAuthors = false,
  error,
  actions,
}: ReviewCardProps) {
  const displayDate = model.date_published ?? model.created_at;
  const authors = model.authors ?? [];

  return (
    <div
      className={cn(
        'group relative p-6 rounded-2xl',
        'flex items-stretch justify-between gap-6',
        'transition-all duration-200',
        'bg-transparent hover:bg-warning/4',
        'hover:shadow-sm hover:shadow-warning/5 hover:-translate-y-px'
      )}
    >
      {/* Left content */}
      <div className="flex-1 min-w-0">
        {/* Badge */}
        <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center px-2 py-0.5',
                'rounded-xs bg-warning',
                'text-white text-[10px] font-bold uppercase tracking-wide'
              )}
            >
              {badge}
            </span>
          </div>
        </div>

        {/* Title */}
        {titleAs === 'link' ? (
          <Link
            to={`/models/${encodeURIComponent(model.id)}`}
            className="text-xl font-bold font-headline text-primary hover:underline"
          >
            {model.name}
          </Link>
        ) : (
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
            {model.name}
          </h3>
        )}

        {/* Subtitle slot */}
        {subtitle}

        {/* Metadata row */}
        <div className="flex items-center gap-4 mt-3 min-h-8">
          <div
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2',
              'text-[11px] text-default-800 uppercase tracking-tight'
            )}
          >
            {showAuthors && authors.length > 0 ? (
              <AuthorListTooltip authors={authors} />
            ) : (
              model.owner && (
                <div className="flex items-center gap-1.5 font-medium text-primary">
                  <UserIcon className="size-3.5" />
                  <span>{model.owner}</span>
                </div>
              )
            )}
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="size-3.5" />
              <span>{formatDateTime(displayDate)}</span>
            </div>
          </div>
        </div>

        {/* Error slot */}
        {error}
      </div>

      {/* Right column — wrapper provided here so callers only supply buttons/modals */}
      <div className="flex flex-col justify-between items-end gap-2">
        {actions}
      </div>
    </div>
  );
}
