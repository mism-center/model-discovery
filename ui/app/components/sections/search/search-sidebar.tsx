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
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import cn from 'classnames';
import { matchSorter } from 'match-sorter';
import { useDebounce } from 'use-debounce';
import { useSearch } from '../../../contexts/search-context';
import type {
  CheckboxConfig,
  DateRangeConfig,
  FilterConfig,
  FilterValue,
  TermAggregation,
} from '../../../api/services/search';
import { MagnifyingGlassIcon } from '@heroicons/react/16/solid';

export function SearchSidebar() {
  const {
    filterConfigs,
    resultType,
    models,
    datasets,
    getFilterValue,
    setFilterValue,
    clearFilter,
  } = useSearch();

  const aggregations =
    resultType === 'models' ? models.aggregations : datasets.aggregations;

  const defaultExpandedKeys = useMemo(() => {
    return filterConfigs
      .filter((c) => c.type !== 'switch')
      .map((config) => config.id);
  }, [filterConfigs]);

  return (
    <div
      className={cn(
        'flex flex-col h-full min-w-[320px]'
        // 'border-l border-slate-200'
      )}
    >
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
        // dividerProps={{ className: 'bg-slate-200' }}
        showDivider={false}
        itemClasses={{
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
        {filterConfigs.map((config, configIndex) => {
          if (config.type === 'switch') {
            const filterValue = getFilterValue(config.id);
            const isSelected =
              filterValue?.type === 'switch' ? filterValue.value : false;
            const count = (
              aggregations?.[config.id] as TermAggregation | undefined
            )?.['true'];

            return (
              <AccordionItem
                key={config.id}
                aria-label={config.label}
                hideIndicator
                classNames={{
                  content: 'hidden',
                  trigger: 'cursor-default',
                  heading: 'px-6',
                }}
                title={
                  <SwitchFilterHeading
                    label={config.label}
                    icon={config.icon}
                    isSelected={isSelected}
                    count={count}
                    onChange={(checked) =>
                      setFilterValue(config.id, {
                        type: 'switch',
                        value: checked,
                      })
                    }
                  />
                }
              />
            );
          }

          return (
            <AccordionItem
              key={config.id}
              aria-label={config.label}
              title={
                <FilterTitle
                  config={config}
                  isActive={!!getFilterValue(config.id)}
                  onClear={() => clearFilter(config.id)}
                />
              }
            >
              {config.type === 'checkbox' && (
                <CheckboxFilter
                  groupIndex={configIndex}
                  config={config}
                  aggregation={
                    aggregations?.[config.id] as TermAggregation | undefined
                  }
                  value={getFilterValue(config.id)}
                  onChange={(selected) =>
                    setFilterValue(config.id, {
                      type: 'checkbox',
                      selected,
                    })
                  }
                />
              )}
              {config.type === 'date_range' && (
                <DateRangeFilter
                  config={config}
                  value={getFilterValue(config.id)}
                  onChange={(start, end) =>
                    setFilterValue(config.id, {
                      type: 'date_range',
                      start,
                      end,
                    })
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

interface FilterTitleProps {
  config: FilterConfig;
  isActive: boolean;
  onClear: () => void;
}

function FilterTitle({ config, isActive, onClear }: FilterTitleProps) {
  return (
    <div className="flex justify-between items-center">
      <div className="flex items-center gap-2 font-headline">
        {config.icon}
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

interface FilterSearchInputProps {
  placeholder: string;
  debounce?: number;
  onChange: (value: string) => void;
}

function FilterSearchInput({
  placeholder,
  onChange,
  debounce = 100,
}: FilterSearchInputProps) {
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

interface SwitchFilterHeadingProps {
  label: string;
  icon: ReactNode;
  isSelected: boolean;
  count: number | undefined;
  onChange: (checked: boolean) => void;
}

function SwitchFilterHeading({
  label,
  icon,
  isSelected,
  count,
  onChange,
}: SwitchFilterHeadingProps) {
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
        {icon}
        <span>{label}</span>
      </div>
      {count !== undefined && (
        <span
          className={cn(
            'flex items-center px-1.5 py-0.5 rounded-full text-xs',
            isSelected
              ? 'text-white bg-primary'
              : 'text-primary bg-primary-100/75'
          )}
        >
          {count}
        </span>
      )}
    </Switch>
  );
}

interface CheckboxFilterProps {
  groupIndex: number;
  config: CheckboxConfig;
  aggregation: TermAggregation | undefined;
  value: FilterValue | undefined;
  onChange: (selected: string[]) => void;
}

function CheckboxFilter({
  groupIndex,
  config,
  aggregation,
  value,
  onChange,
}: CheckboxFilterProps) {
  const [filter, setFilter] = useState('');

  const selected = value?.type === 'checkbox' ? value.selected : [];
  const options = aggregation ? Object.entries(aggregation) : [];
  const loading = aggregation === undefined;

  const filteredOptions = matchSorter(options, filter, {
    keys: [([optionName]) => optionName],
  });

  if (loading)
    return (
      <div className="flex flex-col gap-3 p-0.75">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2.5">
            <Skeleton className="size-4 rounded-xs shrink-0" />
            <Skeleton
              className="h-4 rounded-md"
              // Give each skeleton row a slightly different width so they don't all look uniform.
              // Width is 30% plus a pseudo-random offset (0–28%) based on the row index,
              // shifted by groupIndex so that different filter groups have distinct patterns.
              // Multiplying by 12 and using modulo 29 ensures the offsets cycle through a varied
              // pattern without repeating too predictably.
              style={{ width: `${30 + (((i + groupIndex * 3) * 12) % 29)}%` }}
            />
            <Skeleton className="h-5 w-6 rounded-full ml-auto shrink-0" />
          </div>
        ))}
      </div>
    );

  if (options.length === 0)
    return (
      <span className="text-sm text-default-900">No options available.</span>
    );

  return (
    <div>
      <FilterSearchInput
        placeholder={`Filter ${config.label.toLowerCase()}...`}
        onChange={setFilter}
      />
      <CheckboxGroup value={selected} onChange={onChange} className="p-0.75">
        {filteredOptions.map(([optionName, optionCount]) => (
          <Checkbox
            key={optionName}
            value={optionName}
            color="primary"
            size="sm"
            classNames={{
              wrapper:
                // Checkbox styling
                'rounded-xs before:rounded-xs after:rounded-xs before:border-1 before:bg-white',
              label: cn(
                'ml-0 text-[14px] text-default-900',
                'w-full flex',
                selected.includes(optionName) ? '' : ''
              ),
              base: cn(
                'group py-[6px] -m-[3px] max-w-none rounded-md',
                'transition-colors duration-200',
                'hover:bg-default-100'
              ),
            }}
          >
            <span className="grow">{optionName}</span>
            <span
              className={cn(
                'flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium',
                selected.includes(optionName)
                  ? 'text-white bg-primary'
                  : 'text-primary bg-primary-100/75'
              )}
            >
              {optionCount}
            </span>
          </Checkbox>
        ))}
      </CheckboxGroup>
    </div>
  );
}

interface DateRangeFilterProps {
  config: DateRangeConfig;
  value: FilterValue | undefined;
  onChange: (start?: string, end?: string) => void;
}

function DateRangeFilter({ config, value, onChange }: DateRangeFilterProps) {
  const start =
    value?.type === 'date_range' && value.start
      ? parseDate(value.start)
      : undefined;
  const end =
    value?.type === 'date_range' && value.end
      ? parseDate(value.end)
      : undefined;

  return (
    <div className="flex gap-4 justify-center -mt-1">
      <div>
        <span className="text-xs text-slate-400">Start date:</span>
        <DatePicker
          size="sm"
          // label="Start date"
          value={start ?? null}
          onChange={(date) => onChange(date?.toString(), end?.toString())}
          minValue={parseDate(config.bounds.min)}
          maxValue={end ?? parseDate(config.bounds.max)}
          className="mt-0.5"
          classNames={{
            input: 'text-[13px]',
          }}
        />
      </div>
      <div>
        <span className="text-xs text-slate-400">End date:</span>
        <DatePicker
          size="sm"
          // label="End date"
          value={end ?? null}
          onChange={(date) => onChange(start?.toString(), date?.toString())}
          minValue={start ?? parseDate(config.bounds.min)}
          maxValue={parseDate(config.bounds.max)}
          className="mt-0.5"
          classNames={{
            input: 'text-[13px]',
          }}
        />
      </div>
    </div>
  );
}
