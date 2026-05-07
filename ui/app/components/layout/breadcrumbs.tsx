import { Breadcrumbs, type BreadcrumbsProps } from '@heroui/react';
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
