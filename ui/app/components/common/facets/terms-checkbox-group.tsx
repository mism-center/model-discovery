import { useState } from 'react';
import cn from 'classnames';
import { Checkbox, CheckboxGroup } from '@heroui/react';
import { ChevronDownIcon } from '@heroicons/react/16/solid';
import { matchSorter } from 'match-sorter';

import { FacetSearchInput } from './facet-search-input';

/**
 * How many options to show before collapsing the rest behind "Show all". Only
 * kicks in for the unfiltered list — once the user types a filter, every match
 * is shown (inside the scrollbox) so nothing relevant hides behind the toggle.
 */
const COLLAPSE_AFTER = 8;

export interface TermsBucket {
  /** Stable value stored in state / URL (e.g. a model id). */
  key: string;
  /** Human-readable label shown in the row (defaults to `key`). */
  label?: string;
  /** Count badge. */
  count: number;
}

interface TermsCheckboxGroupProps {
  buckets: TermsBucket[];
  selected: string[];
  onChange: (selected: string[]) => void;
  /** Placeholder for the option-filter input (e.g. "Filter models..."). */
  filterPlaceholder: string;
  /** Message shown when there are no options at all. */
  emptyMessage?: string;
}

/** A single checkbox row: label + count badge, styled to match the facet. */
function TermRow({
  bucket,
  isSelected,
}: {
  bucket: TermsBucket;
  isSelected: boolean;
}) {
  const label = bucket.label ?? bucket.key;
  return (
    <Checkbox
      value={bucket.key}
      color="primary"
      size="sm"
      classNames={{
        // HeroUI positions the hidden input `absolute top-0 w-full h-full` with
        // no inset-inline, so it starts at the row's content edge (inside the
        // row's horizontal padding) yet sizes to the full padding box — sticking
        // out past the row's right edge. Harmless until the list becomes a
        // scrollbox, where it drags in a horizontal scrollbar; pin it instead.
        hiddenInput: 'left-0',
        wrapper:
          'rounded-xs before:rounded-xs after:rounded-xs before:border-1 before:bg-white',
        label: 'ml-0 w-full min-w-0 flex text-[14px] text-default-900',
        base: cn(
          'group py-[6px] -m-[3px] max-w-none rounded-md',
          'transition-colors duration-200',
          'hover:bg-default-100'
        ),
      }}
    >
      {/*
        `min-w-0` + `wrap-anywhere` let a long label wrap instead of forcing the
        row wider than the sidebar. HeroUI's group wrapper is `flex-col
        flex-wrap`, so the flex line's width comes from its widest row's
        min-content — one unbreakable label would stretch every row past the
        scrollbox. `wrap-anywhere` (unlike `break-words`) shrinks that
        min-content, so the line stays inside the sidebar.
      */}
      <span className="grow min-w-0 wrap-anywhere">{label}</span>
      <span
        className={cn(
          // `ms-2` keeps the badge off the label text, which otherwise butts
          // straight up against it once the text fills the row. It belongs here
          // rather than as a `gap` on the label: HeroUI's label slot has a
          // static (non-absolute) 0px-wide `::before`, so it counts as a flex
          // item and a gap would also pad between the checkbox and the text.
          //
          // `self-center shrink-0`: the label is a stretch flex container, so a
          // wrapped multi-line label would otherwise stretch the badge into a
          // tall lozenge (and squeeze it once the text runs long).
          'flex items-center self-center shrink-0 ms-2',
          'px-1.5 py-0.5 rounded-full text-xs font-medium',
          isSelected
            ? 'text-white bg-primary'
            : 'text-primary bg-primary-100/75'
        )}
      >
        {bucket.count}
      </span>
    </Checkbox>
  );
}

/**
 * A multi-select terms facet: a debounced option-filter input over a checkbox
 * list with count badges. Presentational and search-agnostic — it operates on
 * plain `TermsBucket`s so both the search sidebar (from API aggregations) and
 * the runs sidebar (from client-derived counts) can share the styling.
 *
 * The option-filter fuzzy-matches on the bucket label (falling back to key),
 * mirroring the search sidebar's behavior. Long lists collapse to
 * `COLLAPSE_AFTER` rows behind a "Show all" toggle that expands into a
 * fixed-height scrollbox; while filtering, all matches show in the scrollbox.
 */
export function TermsCheckboxGroup({
  buckets,
  selected,
  onChange,
  filterPlaceholder,
  emptyMessage = 'No options available.',
}: TermsCheckboxGroupProps) {
  const [filter, setFilter] = useState('');
  const [showAll, setShowAll] = useState(false);

  if (buckets.length === 0) {
    return <span className="text-sm text-default-900">{emptyMessage}</span>;
  }

  const filtered = matchSorter(buckets, filter, {
    keys: [(b) => b.label ?? b.key],
  });

  const isFiltering = filter.trim().length > 0;
  // Collapse only the unfiltered list. While filtering, show every match (in
  // the scrollbox) so relevant options never hide behind "Show all".
  const collapsed =
    !isFiltering && !showAll && filtered.length > COLLAPSE_AFTER;
  const visible = collapsed ? filtered.slice(0, COLLAPSE_AFTER) : filtered;
  // Scroll the list when it's long: whenever expanded, or when actively
  // filtering to many matches. A collapsed 8-row list needs no scrollbox.
  const scroll = !collapsed && filtered.length > COLLAPSE_AFTER;

  return (
    <div>
      <FacetSearchInput placeholder={filterPlaceholder} onChange={setFilter} />
      <CheckboxGroup
        value={selected}
        onChange={onChange}
        // `w-0 min-w-full`: the sidebar sits in an `auto` grid column, so its
        // width is the max-content of its contents — a long label would widen
        // the whole sidebar. A definite `w-0` drops this list's max-content
        // contribution to zero, and `min-w-full` then lays it out at the
        // sidebar's real width, so labels wrap to fit instead of pushing.
        //
        // The rows bleed 3px into `p-0.75` (negative margins, to keep the list
        // compact and the hover fill full-width), so the box may only ever
        // scroll vertically. `overflow-y-auto` alone would imply
        // `overflow-x: auto`, turning that bleed into a horizontal scrollbar, so
        // pin the x axis; rows end exactly at the padding edge, so nothing is
        // cut off. (`clip` would be the stricter choice, but CSS computes it
        // back to `hidden` whenever the other axis scrolls.)
        className={cn(
          'p-0.75 w-0 min-w-full',
          scroll && 'max-h-80 overflow-y-auto overflow-x-hidden'
        )}
      >
        {visible.map((bucket) => (
          <TermRow
            key={bucket.key}
            bucket={bucket}
            isSelected={selected.includes(bucket.key)}
          />
        ))}
      </CheckboxGroup>

      {!isFiltering && filtered.length > COLLAPSE_AFTER && (
        <button
          type="button"
          onClick={() => setShowAll((open) => !open)}
          className="mt-1 flex items-center gap-1 text-[13px] font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
        >
          <ChevronDownIcon
            aria-hidden="true"
            className={cn(
              'size-3.5 transition-transform',
              showAll && 'rotate-180'
            )}
          />
          {showAll ? 'Show less' : `Show all (${filtered.length})`}
        </button>
      )}
    </div>
  );
}
