import { Breadcrumbs, type BreadcrumbsProps } from '@heroui/react';
import { ChevronRightIcon } from '@heroicons/react/16/solid';
import cn from 'classnames';

export default function BreadcrumbsNav({
  classNames,
  itemClasses,
  children,
  ...props
}: BreadcrumbsProps) {
  return (
    <Breadcrumbs
      classNames={{
        ...classNames,
        list: cn('p-6 py-3 shadow-sm bg-secondary-400', classNames?.list),
      }}
      itemClasses={{
        ...itemClasses,
        item: cn(
          'text-default-100 data-[current=true]:font-semibold data-[current=true]:text-white',
          itemClasses?.item
        ),
        separator: cn('text-default-100', itemClasses?.separator),
      }}
      radius="none"
      underline="hover"
      {...props}
    >
      {children}
    </Breadcrumbs>
  );
}

/**
 * Breadcrumbs for light/white page backgrounds (compact search header, runs
 * page, etc.), as opposed to the hero-banner variant above.
 */
export function CompactBreadcrumbs({
  itemClasses,
  children,
  ...props
}: BreadcrumbsProps) {
  return (
    <Breadcrumbs
      separator={<ChevronRightIcon className="size-3.5" />}
      itemClasses={{
        ...itemClasses,
        item: cn(
          'text-[13px] font-medium text-default-800',
          'transition-colors hover:text-primary',
          'data-[current=true]:text-primary data-[current=true]:font-semibold',
          itemClasses?.item
        ),
        separator: cn('text-default-600 mx-0.5', itemClasses?.separator),
      }}
      {...props}
    >
      {children}
    </Breadcrumbs>
  );
}
