import cn from 'classnames';
import { Switch } from '@heroui/react';

interface ToggleFacetHeadingProps {
  label: string;
  isSelected: boolean;
  onChange: (checked: boolean) => void;
}

/**
 * A boolean facet rendered as a Switch in an accordion heading (no expandable
 * body). Presentational and search-agnostic — shared by the search and runs
 * sidebars.
 */
export function ToggleFacetHeading({
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
