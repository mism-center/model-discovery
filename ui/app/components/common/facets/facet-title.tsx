import cn from 'classnames';
import { Button } from '@heroui/react';

interface FacetTitleProps {
  label: string;
  isActive: boolean;
  onClear: () => void;
}

/**
 * An accordion-item title: the facet label plus a Clear button that only
 * shows when the facet has an active selection. Presentational and
 * search-agnostic — shared by the search and runs sidebars.
 */
export function FacetTitle({ label, isActive, onClear }: FacetTitleProps) {
  return (
    // Fixed row height so the Clear button (taller than the label alone)
    // doesn't resize the heading when it appears/disappears.
    <div className="flex justify-between items-center h-6">
      <div className="flex items-center gap-2 font-headline">
        <span>{label}</span>
      </div>
      {/* `invisible` (not `hidden`) keeps the button's box reserved so the row
          height stays constant whether or not a filter is active. */}
      <Button
        as="span"
        onPress={onClear}
        variant="light"
        className={cn(
          'min-w-0 h-6 w-12 text-[13px] font-medium text-slate-700',
          !isActive && 'invisible pointer-events-none'
        )}
      >
        Clear
      </Button>
    </div>
  );
}
