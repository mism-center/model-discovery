import { motion } from 'framer-motion';
import { Pagination } from '@heroui/react';
import { useSearch } from '~/search/context/search-context';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { SearchResult } from './search-result';
import { ResultSkeleton } from './skeleton';
import { SearchResultsHeader } from './search-header';

const motionTransition = {
  type: 'spring',
  bounce: 0,
  duration: 0.3,
} as const;

function SearchResultsContent() {
  const { state, data, isLoading, error, refetch } = useSearch();

  if (error) {
    return (
      <ApiErrorDisplay error={error} title="Search failed" onRetry={refetch} />
    );
  }

  return (
    <motion.div
      key={state.resourceType}
      transition={motionTransition}
      className="flex flex-col gap-2"
    >
      {isLoading &&
        Array.from({ length: 5 }).map((_, i) => (
          <motion.div
            key={i}
            layout
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={motionTransition}
          >
            <ResultSkeleton />
          </motion.div>
        ))}
      {!isLoading &&
        data?.results.map((result) => (
          <SearchResult key={result.id} result={result} />
        ))}
    </motion.div>
  );
}

function SearchResultsPagination() {
  const { state, data, isLoading, setOffset } = useSearch();

  if (!data || isLoading) return null;

  const { total } = data;
  const { offset, limit } = state;
  const totalPages = Math.ceil(total / limit);

  if (totalPages <= 1) return null;

  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="flex justify-center mt-8">
      <Pagination
        total={totalPages}
        page={currentPage}
        onChange={(page) => setOffset((page - 1) * limit)}
        showControls
        classNames={{
          cursor: 'bg-primary text-white font-bold',
          prev: 'data-[disabled=true]:text-default-600',
          next: 'data-[disabled=true]:text-default-600',
        }}
      />
    </div>
  );
}

export function SearchResults() {
  return (
    <div className="flex flex-col w-full grow p-10">
      <SearchResultsHeader />
      <SearchResultsContent />
      <SearchResultsPagination />
    </div>
  );
}
