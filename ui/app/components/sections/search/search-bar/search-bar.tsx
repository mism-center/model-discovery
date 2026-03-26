import { useEffect, useState } from 'react';
import { BreadcrumbItem, Button, Input } from '@heroui/react';
import { MagnifyingGlassIcon } from '@heroicons/react/16/solid';
import cn from 'classnames';
import BreadcrumbsNav from '~/components/layout/breadcrumbs';
import { useSearch } from '../../../../contexts/search-context';
import { SuggestedTermsContainer } from './suggested-terms';
import { AIModeCard } from './ai-mode-card';

export function SearchBar() {
  const { searchQuery, isCompact, doSearch } = useSearch();

  const [currentSearch, setCurrentSearch] = useState(searchQuery);

  // Sync local input state with URL when it changes externally
  useEffect(() => {
    setCurrentSearch(searchQuery);
  }, [searchQuery]);

  return (
    <div
      className={cn('grid', isCompact ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]')}
      style={{
        transitionProperty: 'grid-template-rows',
        transitionDuration: '300ms',
        transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      <div
        className="overflow-hidden"
        style={{
          opacity: isCompact ? 0 : 1,
          transitionProperty: 'opacity',
          transitionDuration: '200ms',
          transitionTimingFunction: 'ease-in-out',
          transitionDelay: isCompact ? '0ms' : '0ms',
        }}
      >
        <form
          className="w-full relative border-b border-default bg-primary-gradient pt-4 pb-12 px-6"
          onSubmit={(e) => {
            e.preventDefault();
            doSearch(currentSearch);
          }}
        >
          <div
            className="absolute inset-0 pointer-events-none opacity-[0.025]"
            style={{
              backgroundImage: `linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)`,
              backgroundSize: '40px 40px',
            }}
          />

          <div className="relative z-10 mx-auto w-full px-4 2xl:px-24 max-w-500 lg:px-24">
            <BreadcrumbsNav
              classNames={{ list: 'bg-transparent px-0 py-6 shadow-none' }}
              itemClasses={{
                item: 'text-xs font-medium tracking-wide uppercase text-secondary-300',
              }}
            >
              <BreadcrumbItem href="/">Home</BreadcrumbItem>
              <BreadcrumbItem>Search</BreadcrumbItem>
            </BreadcrumbsNav>
            <div className="flex flex-col items-stretch lg:flex-row lg:items-center">
              <div className="flex-1 w-full">
                <h1 className="text-4xl md:text-5xl lg:text-[56px] font-bold tracking-tight text-white leading-[1.1] mb-6">
                  Find{' '}
                  <span className="text-gradient-success-secondary">
                    models
                  </span>{' '}
                  &{' '}
                  <span className="text-gradient-success-secondary">
                    data
                  </span>{' '}
                  across scales
                </h1>
                <div className="relative w-full flex items-center group">
                  <div
                    className={cn(
                      'flex items-center w-full gap-2',
                      'p-1 shadow-lg shadow-glass backdrop-blur-md rounded-lg',
                      'bg-white border border-white/20',
                      'focus-within:ring-2 focus-within:ring-slate-300',
                      'transition-all duration-200'
                    )}
                  >
                    <Input
                      classNames={{
                        input:
                          'text-[16px] !text-black tracking-wide font-light placeholder-default-700',
                        inputWrapper: 'shadow-none bg-transparent! pl-3',
                      }}
                      placeholder="Search for keywords, ontology terms, or authors..."
                      value={currentSearch}
                      onValueChange={setCurrentSearch}
                      startContent={
                        <MagnifyingGlassIcon className="mr-2 size-7 text-default-700" />
                      }
                    />
                    <Button
                      className="font-bold h-12 px-7 rounded-lg"
                      color="primary"
                      onPress={() => doSearch(currentSearch)}
                    >
                      Search
                    </Button>
                  </div>
                </div>
                <SuggestedTermsContainer doSearch={doSearch} />
              </div>
              <div
                className={cn(
                  'shrink-0 w-full lg:w-[400px]',
                  'mt-12 lg:mt-0 lg:ml-12',
                )}
              >
                <AIModeCard />
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
