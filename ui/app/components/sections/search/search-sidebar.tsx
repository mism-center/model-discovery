import { Accordion, AccordionItem, DatePicker, Skeleton } from '@heroui/react';
import { parseDate } from '@internationalized/date';
import { useMemo } from 'react';
import cn from 'classnames';

import type { AggResult } from '~/api';
import {
  FacetTitle,
  ToggleFacetHeading,
  TermsCheckboxGroup,
} from '~/components/common/facets';
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
                  label={facet.label}
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
  const selected = value?.kind === 'terms' ? value.values : [];
  // The API may not include the requested facet in `aggs` yet (e.g. before
  // the first response lands). Treat that as a loading state rather than
  // "no options".
  const loading = aggregation === undefined;
  const buckets = aggregation?.buckets ?? [];

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

  return (
    <TermsCheckboxGroup
      buckets={buckets.map((b) => ({
        key: b.key,
        label: b.key.charAt(0).toUpperCase() + b.key.slice(1),
        count: b.count,
      }))}
      selected={selected}
      onChange={onChange}
      filterPlaceholder={`Filter ${config.label.toLowerCase()}...`}
    />
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
