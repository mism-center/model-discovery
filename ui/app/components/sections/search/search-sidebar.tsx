import {
  Accordion,
  AccordionItem,
  Button,
  Checkbox,
  CheckboxGroup,
  DatePicker,
  Input,
  Skeleton,
  Switch,
} from '@heroui/react';
import { parseDate } from '@internationalized/date';
import { useEffect, useMemo, useState } from 'react';
import cn from 'classnames';
import { matchSorter } from 'match-sorter';
import { useDebounce } from 'use-debounce';
import { MagnifyingGlassIcon } from '@heroicons/react/16/solid';

import type { AggResult } from '~/api';
import { useSearch } from '~/search/context/search-context';
import {
  facetsForResourceType,
  type FacetConfig,
} from '~/search/state/facets.config';
import type { FacetValue } from '~/search/state/types';

export function SearchSidebar() {
  const { state, data, setFacet, clearFacet } = useSearch();

  const facets = useMemo(
    () => facetsForResourceType(state.resourceType),
    [state.resourceType]
  );

  const defaultExpandedKeys = useMemo(
    () => facets.filter((f) => f.widget !== 'toggle').map((f) => f.id),
    [facets]
  );

  return (
    <div className="flex flex-col h-full min-w-[320px]">
      <div className="mb-4 p-6 pb-0">
        <h2 className="text-black font-headline font-bold text-[14px] uppercase tracking-widest mb-1">
          Filters
        </h2>
        <p className="text-slate-600 text-[12px]">
          Refine your search parameters
        </p>
      </div>
      <Accordion
        selectionMode="multiple"
        defaultExpandedKeys={defaultExpandedKeys}
        showDivider={false}
        itemClasses={{
          base: 'pb-2',
          heading: 'py-0 group px-6',
          content: 'pt-0 pb-4 px-6',
          trigger: 'gap-2 flex-row',
          title: 'text-[14px] font-medium text-slate-700',
          indicator: cn(
            'text-gray-500',
            'rotate-180 data-[open=true]:rotate-270'
          ),
        }}
        className="p-0"
      >
        {facets.map((facet, index) => {
          const agg = data?.aggs?.[facet.field];
          const value = state.facets[facet.id];

          if (facet.widget === 'toggle') {
            const isSelected = value?.kind === 'toggle' ? value.value : false;
            return (
              <AccordionItem
                key={facet.id}
                aria-label={facet.label}
                hideIndicator
                classNames={{
                  content: 'hidden',
                  trigger: 'cursor-default',
                  heading: 'px-6',
                }}
                title={
                  <ToggleFacetHeading
                    label={facet.label}
                    isSelected={isSelected}
                    onChange={(checked) =>
                      setFacet(
                        facet.id,
                        checked ? { kind: 'toggle', value: true } : undefined
                      )
                    }
                  />
                }
              />
            );
          }

          return (
            <AccordionItem
              key={facet.id}
              aria-label={facet.label}
              title={
                <FacetTitle
                  config={facet}
                  isActive={Boolean(value)}
                  onClear={() => clearFacet(facet.id)}
                />
              }
            >
              {facet.widget === 'terms' && (
                <TermsFacet
                  groupIndex={index}
                  config={facet}
                  aggregation={agg}
                  value={value}
                  onChange={(selected) =>
                    setFacet(
                      facet.id,
                      selected.length > 0
                        ? { kind: 'terms', values: selected }
                        : undefined
                    )
                  }
                />
              )}
              {facet.widget === 'range' && (
                <RangeFacet
                  value={value}
                  onChange={(from, to) =>
                    setFacet(
                      facet.id,
                      from || to ? { kind: 'range', from, to } : undefined
                    )
                  }
                />
              )}
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface FacetTitleProps {
  config: FacetConfig;
  isActive: boolean;
  onClear: () => void;
}

function FacetTitle({ config, isActive, onClear }: FacetTitleProps) {
  return (
    <div className="flex justify-between items-center">
      <div className="flex items-center gap-2 font-headline">
        <span>{config.label}</span>
      </div>
      <Button
        as="span"
        onPress={onClear}
        variant="light"
        className={cn(
          'min-w-0 h-6 w-12 text-[13px] font-medium text-slate-700',
          !isActive && 'hidden'
        )}
      >
        Clear
      </Button>
    </div>
  );
}

interface FacetSearchInputProps {
  placeholder: string;
  debounce?: number;
  onChange: (value: string) => void;
}

function FacetSearchInput({
  placeholder,
  onChange,
  debounce = 100,
}: FacetSearchInputProps) {
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search, debounce);

  useEffect(() => {
    onChange(debouncedSearch);
  }, [debouncedSearch, onChange]);

  return (
    <Input
      classNames={{
        input: 'text-[13px]',
        inputWrapper: cn(
          'min-h-8 h-8 mb-2',
          'bg-white! border border-default-300 shadow-none rounded-md',
          'hover:border-default-500',
          'focus-within:border-default-600! focus-within:ring-2 focus-within:ring-default-200',
          'transition-all duration-200'
        ),
      }}
      radius="none"
      value={search}
      onValueChange={setSearch}
      placeholder={placeholder}
      startContent={
        <MagnifyingGlassIcon className="size-4 text-slate-400 mr-1" />
      }
    />
  );
}

interface ToggleFacetHeadingProps {
  label: string;
  isSelected: boolean;
  onChange: (checked: boolean) => void;
}

function ToggleFacetHeading({
  label,
  isSelected,
  onChange,
}: ToggleFacetHeadingProps) {
  return (
    <Switch
      size="sm"
      color="primary"
      isSelected={isSelected}
      onValueChange={onChange}
      classNames={{
        base: cn(
          'flex-row-reverse w-[calc(100%+24px)] max-w-none justify-between',
          'rounded-lg -mx-3 -my-4 p-3 py-4',
          'hover:bg-default-100',
          'transition-all duration-200 pointer-events-auto'
        ),
        label:
          'text-[14px] font-headline text-slate-700 flex items-center gap-2 ml-0',
      }}
    >
      <div className="flex items-center gap-2">
        <span>{label}</span>
      </div>
    </Switch>
  );
}

interface TermsFacetProps {
  groupIndex: number;
  config: FacetConfig;
  aggregation: AggResult | undefined;
  value: FacetValue | undefined;
  onChange: (selected: string[]) => void;
}

function TermsFacet({
  groupIndex,
  config,
  aggregation,
  value,
  onChange,
}: TermsFacetProps) {
  const [filter, setFilter] = useState('');

  const selected = value?.kind === 'terms' ? value.values : [];
  // The API may not include the requested facet in `aggs` yet (e.g. before
  // the first response lands). Treat that as a loading state rather than
  // "no options".
  const loading = aggregation === undefined;
  const buckets = aggregation?.buckets ?? [];

  const filteredBuckets = matchSorter(buckets, filter, {
    keys: [(b) => b.key],
  });

  if (loading) {
    return (
      <div className="flex flex-col gap-3 p-0.75">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2.5">
            <Skeleton className="size-4 rounded-xs shrink-0" />
            <Skeleton
              className="h-4 rounded-md"
              // Varied widths so rows don't look uniform. 30% + pseudo-random
              // offset derived from row index + groupIndex.
              style={{ width: `${30 + (((i + groupIndex * 3) * 12) % 29)}%` }}
            />
            <Skeleton className="h-5 w-6 rounded-full ml-auto shrink-0" />
          </div>
        ))}
      </div>
    );
  }

  if (buckets.length === 0) {
    return (
      <span className="text-sm text-default-900">No options available.</span>
    );
  }

  return (
    <div>
      <FacetSearchInput
        placeholder={`Filter ${config.label.toLowerCase()}...`}
        onChange={setFilter}
      />
      <CheckboxGroup value={selected} onChange={onChange} className="p-0.75">
        {filteredBuckets.map((bucket) => (
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
            <span className="grow">
              {bucket.key.charAt(0).toUpperCase() + bucket.key.slice(1)}
            </span>
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
        ))}
      </CheckboxGroup>
    </div>
  );
}

interface RangeFacetProps {
  value: FacetValue | undefined;
  onChange: (from?: string, to?: string) => void;
}

/**
 * Date range facet.
 * The API currently only has date ranges, if a numeric-range facet ever
 * appears this will need augmenting.
 *
 * No min/max bounds are enforced, backend doesn't expose these yet.
 */
function RangeFacet({ value, onChange }: RangeFacetProps) {
  const from =
    value?.kind === 'range' && value.from ? parseDate(value.from) : null;
  const to = value?.kind === 'range' && value.to ? parseDate(value.to) : null;

  return (
    <div className="flex gap-4 justify-center -mt-1">
      <div>
        <span className="text-xs text-slate-400">From:</span>
        <DatePicker
          size="sm"
          // @ts-expect-error HeroUI's DatePicker makes it impossible to pull the same copies from @internationalized/date
          value={from}
          onChange={(date: ReturnType<typeof parseDate> | null) =>
            onChange(date?.toString(), to?.toString() ?? undefined)
          }
          maxValue={to ?? undefined}
          className="mt-0.5"
          classNames={{ input: 'text-[13px]' }}
        />
      </div>
      <div>
        <span className="text-xs text-slate-400">To:</span>
        <DatePicker
          size="sm"
          // @ts-expect-error HeroUI's DatePicker makes it impossible to pull the same copies from @internationalized/date
          value={to}
          onChange={(date: ReturnType<typeof parseDate> | null) =>
            onChange(from?.toString() ?? undefined, date?.toString())
          }
          minValue={from ?? undefined}
          className="mt-0.5"
          classNames={{ input: 'text-[13px]' }}
        />
      </div>
    </div>
  );
}
