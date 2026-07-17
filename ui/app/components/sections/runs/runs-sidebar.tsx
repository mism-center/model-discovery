import { useMemo } from 'react';
import { Accordion, AccordionItem, Chip, DatePicker } from '@heroui/react';
import { parseDate } from '@internationalized/date';
import cn from 'classnames';

import type { UserRunItem } from '~/api/endpoints/runs';
import {
  FacetTitle,
  ToggleFacetHeading,
  TermsCheckboxGroup,
} from '~/components/common/facets';
import { modelBuckets, type RunFilters } from './run-filters';

interface RunsSidebarProps {
  /** Full (unfiltered) run list — the source for model options + counts. */
  runs: UserRunItem[];
  filters: RunFilters;
  onModelsChange: (models: string[]) => void;
  onDateChange: (from?: string, to?: string) => void;
  onHasOutputsChange: (value: boolean) => void;
}

/**
 * ISO date (YYYY-MM-DD) `n` days before today, in UTC.
 *
 * Must be UTC: `applyFilters` compares against `run.created_at.slice(0, 10)`,
 * which is the UTC calendar date of the server timestamp. Deriving the bound
 * from local time would skew the comparison by a day near midnight.
 */
function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

const DATE_PRESETS: { label: string; days: number }[] = [
  { label: 'Today', days: 0 },
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
];

const ACCORDION_ITEM_CLASSES = {
  base: 'pb-2',
  heading: 'py-0 group px-6',
  content: 'pt-0 pb-4 px-6',
  trigger: 'gap-2 flex-row',
  title: 'text-[14px] font-medium text-slate-700',
  indicator: cn('text-gray-500', 'rotate-180 data-[open=true]:rotate-270'),
};

export function RunsSidebar({
  runs,
  filters,
  onModelsChange,
  onDateChange,
  onHasOutputsChange,
}: RunsSidebarProps) {
  const buckets = useMemo(() => modelBuckets(runs, filters), [runs, filters]);

  const dateActive = Boolean(filters.from || filters.to);
  // Which preset (if any) is currently selected: matches when `from` equals the
  // preset's start date and there's no custom `to`.
  const activePreset = useMemo(() => {
    if (filters.to) return;
    return DATE_PRESETS.find((p) => filters.from === isoDaysAgo(p.days))?.label;
  }, [filters.from, filters.to]);

  const fromValue = filters.from ? parseDate(filters.from) : null;
  const toValue = filters.to ? parseDate(filters.to) : null;

  return (
    <div className="flex flex-col h-full min-w-[320px]">
      <div className="mb-4 p-6 pb-0">
        <h2 className="text-black font-headline font-bold text-[14px] uppercase tracking-widest mb-1">
          Filters
        </h2>
        <p className="text-slate-600 text-[12px]">Refine your run history</p>
      </div>

      <Accordion
        selectionMode="multiple"
        defaultExpandedKeys={['model', 'created']}
        showDivider={false}
        itemClasses={ACCORDION_ITEM_CLASSES}
        className="p-0"
      >
        <AccordionItem
          key="model"
          aria-label="Model"
          title={
            <FacetTitle
              label="Model"
              isActive={filters.models.length > 0}
              onClear={() => onModelsChange([])}
            />
          }
        >
          <TermsCheckboxGroup
            buckets={buckets.map((b) => ({
              key: b.id,
              label: b.name,
              count: b.count,
            }))}
            selected={filters.models}
            onChange={onModelsChange}
            filterPlaceholder="Filter models..."
            emptyMessage="No models to filter."
          />
        </AccordionItem>

        <AccordionItem
          key="created"
          aria-label="Created"
          title={
            <FacetTitle
              label="Created"
              isActive={dateActive}
              onClear={() => onDateChange()}
            />
          }
        >
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              {DATE_PRESETS.map((preset) => {
                const selected = activePreset === preset.label;
                return (
                  <Chip
                    key={preset.label}
                    as="button"
                    variant={selected ? 'solid' : 'flat'}
                    color={selected ? 'primary' : 'default'}
                    size="sm"
                    className={cn(
                      'cursor-pointer',
                      !selected &&
                        'text-default-900 font-medium hover:bg-default-200'
                    )}
                    onClick={() =>
                      selected
                        ? onDateChange()
                        : onDateChange(isoDaysAgo(preset.days))
                    }
                  >
                    {preset.label}
                  </Chip>
                );
              })}
            </div>

            <div className="flex gap-4 justify-center">
              <div>
                <span className="text-xs text-slate-400">From:</span>
                <DatePicker
                  size="sm"
                  // @ts-expect-error HeroUI's DatePicker makes it impossible to pull the same copies from @internationalized/date
                  value={fromValue}
                  onChange={(date: ReturnType<typeof parseDate> | null) =>
                    onDateChange(date?.toString(), toValue?.toString())
                  }
                  maxValue={toValue ?? undefined}
                  className="mt-0.5"
                  classNames={{ input: 'text-[13px]' }}
                />
              </div>
              <div>
                <span className="text-xs text-slate-400">To:</span>
                <DatePicker
                  size="sm"
                  // @ts-expect-error HeroUI's DatePicker makes it impossible to pull the same copies from @internationalized/date
                  value={toValue}
                  onChange={(date: ReturnType<typeof parseDate> | null) =>
                    onDateChange(fromValue?.toString(), date?.toString())
                  }
                  minValue={fromValue ?? undefined}
                  className="mt-0.5"
                  classNames={{ input: 'text-[13px]' }}
                />
              </div>
            </div>
          </div>
        </AccordionItem>

        <AccordionItem
          key="outputs"
          aria-label="Has outputs"
          hideIndicator
          classNames={{
            content: 'hidden',
            trigger: 'cursor-default',
            heading: 'px-6',
          }}
          title={
            <ToggleFacetHeading
              label="Has outputs"
              isSelected={filters.hasOutputs}
              onChange={onHasOutputsChange}
            />
          }
        />
      </Accordion>
    </div>
  );
}
