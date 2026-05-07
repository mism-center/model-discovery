import { motion } from 'framer-motion';
import { Pagination } from '@heroui/react';
import { useSearch } from '~/contexts/search-context';
import { SearchResult } from './search-result';
import { ResultSkeleton } from './skeleton';
import { SearchResultsHeader } from './search-header';

const motionTransition = {
  type: 'spring',
  bounce: 0,
  duration: 0.3,
} as const;

function SearchResultsContent() {
  const { resultType, models, datasets } = useSearch();
  const active = resultType === 'models' ? models : datasets;

  if (active.error) return <span>Encountered an unexpected search error.</span>;
  if (!active.isLoading && !active.results) return null;

  return (
    <motion.div
      key={resultType}
      transition={motionTransition}
      className="flex flex-col gap-2"
    >
      {active.isLoading &&
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
      {!active.isLoading &&
        active.results?.map((result) => (
          <SearchResult
            key={result.id}
            result={result}
            resultType={resultType}
          />
        ))}
    </motion.div>
  );
}

function SearchResultsPagination() {
  const { resultType, models, datasets, setPage } = useSearch();
  const active = resultType === 'models' ? models : datasets;

  if (!active.pagination || active.isLoading) return null;

  const { offset, limit, total } = active.pagination;
  const totalPages = Math.ceil(total / limit);

  if (totalPages <= 1) return null;

  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="flex justify-center mt-8">
      <Pagination
        total={totalPages}
        page={currentPage}
        onChange={(page) => setPage((page - 1) * limit)}
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
