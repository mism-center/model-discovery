import {
  BreadcrumbItem,
  Breadcrumbs,
  Select,
  SelectItem,
  Tab,
  Tabs,
} from '@heroui/react';
import cn from 'classnames';
import { useSearch } from '~/contexts/search-context';
import type { ResultType, SortOrder } from '~/api/services/search';

export function SearchResultsHeader() {
  const {
    searchQuery,
    isCompact,
    resultType,
    sort,
    models,
    datasets,
    setResultType,
    setSort,
  } = useSearch();

  const modelsTotal = models.pagination?.total;
  const datasetsTotal = datasets.pagination?.total;
  const totalResults = (modelsTotal ?? 0) + (datasetsTotal ?? 0);

  return (
    <div>
      <div className="flex justify-between items-end mb-8">
        <div>
          {isCompact && (
            <Breadcrumbs
              itemClasses={{
                item: cn(
                  'text-[13px]',
                  'data-[current=true]:text-primary data-[current=true]:font-medium'
                ),
              }}
              className="mb-2"
            >
              <BreadcrumbItem href="/">Home</BreadcrumbItem>
              <BreadcrumbItem>Search</BreadcrumbItem>
            </Breadcrumbs>
          )}
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            {isCompact ? 'Search Results' : 'Featured Submissions'}
          </h1>
          {isCompact && (
            <p className="mt-3 text-[16px] font-medium text-default-800/90">
              Found {totalResults} results for{' '}
              <span className="text-secondary font-bold">
                &quot;{searchQuery}&quot;
              </span>
            </p>
          )}
        </div>
      </div>
      <div className="flex justify-between mb-4">
        <Tabs
          aria-label="Result types"
          selectedKey={resultType}
          onSelectionChange={(key) => setResultType(key as ResultType)}
          classNames={{
            base: 'flex w-full border-b border-default-200/75',
            tabList: 'p-0 gap-0',
            tab: cn(
              'w-auto pt-0 pb-4 px-6 h-10',
              'border-b-2 border-transparent data-[selected=true]:border-primary',
              'hover:text-primary',
              'opacity-100! active:opacity-80!',
              'transition-all duration-200'
            ),
            tabContent: cn(
              'text-[17px] font-extrabold text-default-800/90 group-data-[selected=true]:text-primary',
              'group-hover:text-primary/85'
            ),
            cursor: 'hidden',
          }}
          variant="underlined"
        >
          <Tab
            key="models"
            title={
              <div className="flex items-center gap-3">
                Models{' '}
                {modelsTotal !== undefined && (
                  <span className="text-sm font-bold text-default-700/75">
                    {modelsTotal}
                  </span>
                )}
              </div>
            }
          />
          <Tab
            key="datasets"
            title={
              <div className="flex items-center gap-3">
                Datasets{' '}
                {datasetsTotal !== undefined && (
                  <span className="text-sm font-bold text-default-700/75">
                    {datasetsTotal}
                  </span>
                )}
              </div>
            }
          />
        </Tabs>
        {isCompact && (
          <div className="flex justify-end grow gap-4 px-4 border-b border-slate-200">
            <Select
              label="Sort by:"
              labelPlacement="outside-left"
              variant="underlined"
              selectedKeys={[sort]}
              onChange={(e) => {
                if (e.target.value) setSort(e.target.value as SortOrder);
              }}
              classNames={{
                base: 'w-auto items-end',
                innerWrapper: 'w-auto',
                trigger: 'items-end shadow-none border-box !pb-2.5',
                selectorIcon: 'relative left-0 ml-1 mb-0.5',
                label: 'text-[14px] text-slate-500 pb-2.5',
                value:
                  'overflow-visible text-[14px] text-primary! font-semibold',
              }}
              popoverProps={{
                placement: 'bottom-end',
                radius: 'none',
                className: 'min-w-fit',
                classNames: { content: 'p-0 rounded-sm' },
                // Select enforces a popover width that does not fit its content for some reason.
                style: { minWidth: 'fit-content' },
              }}
              listboxProps={{
                // List items have no slots...
                className: cn(
                  'w-auto p-1',
                  '[&_li]:rounded-sm [&_li]:gap-6 [&_li]:py-2',
                  '[&_li]:bg-transparent!',
                  '[&_span]:text-[15px]!',
                  '[&_li]:hover:bg-default-100!',
                  '[&_li]:active:bg-default-200!',
                  '[&_li]:data-[selected=true]:bg-default-300!'
                ),
              }}
            >
              <SelectItem key="relevance">Relevance</SelectItem>
              <SelectItem key="featured">Featured</SelectItem>
              <SelectItem key="latest">Latest</SelectItem>
            </Select>
          </div>
        )}
      </div>
    </div>
  );
}
