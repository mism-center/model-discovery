import { useState } from 'react';
import cn from 'classnames';
import { Checkbox, CheckboxGroup } from '@heroui/react';
import { matchSorter } from 'match-sorter';

import { FacetSearchInput } from './facet-search-input';

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

/**
 * A multi-select terms facet: a debounced option-filter input over a checkbox
 * list with count badges. Presentational and search-agnostic — it operates on
 * plain `TermsBucket`s so both the search sidebar (from API aggregations) and
 * the runs sidebar (from client-derived counts) can share the styling.
 *
 * The option-filter fuzzy-matches on the bucket label (falling back to key),
 * mirroring the search sidebar's behavior.
 */
export function TermsCheckboxGroup({
  buckets,
  selected,
  onChange,
  filterPlaceholder,
  emptyMessage = 'No options available.',
}: TermsCheckboxGroupProps) {
  const [filter, setFilter] = useState('');

  if (buckets.length === 0) {
    return <span className="text-sm text-default-900">{emptyMessage}</span>;
  }

  const filtered = matchSorter(buckets, filter, {
    keys: [(b) => b.label ?? b.key],
  });

  return (
    <div>
      <FacetSearchInput placeholder={filterPlaceholder} onChange={setFilter} />
      <CheckboxGroup value={selected} onChange={onChange} className="p-0.75">
        {filtered.map((bucket) => {
          const label = bucket.label ?? bucket.key;
          return (
            <Checkbox
              key={bucket.key}
              value={bucket.key}
              color="primary"
              size="sm"
              classNames={{
                wrapper:
                  'rounded-xs before:rounded-xs after:rounded-xs before:border-1 before:bg-white',
                label: 'ml-0 w-full flex text-[14px] text-default-900',
                base: cn(
                  'group py-[6px] -m-[3px] max-w-none rounded-md',
                  'transition-colors duration-200',
                  'hover:bg-default-100'
                ),
              }}
            >
              <span className="grow">{label}</span>
              <span
                className={cn(
                  'flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium',
                  selected.includes(bucket.key)
                    ? 'text-white bg-primary'
                    : 'text-primary bg-primary-100/75'
                )}
              >
                {bucket.count}
              </span>
            </Checkbox>
          );
        })}
      </CheckboxGroup>
    </div>
  );
}
