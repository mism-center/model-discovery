import { motion } from 'framer-motion';
import { Pagination } from '@heroui/react';
import { useSearch } from '~/search/context/search-context';
import type { SearchResultItem } from '~/api';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { SearchResult } from './search-result';
import { PendingReviewCard } from './pending-review-card';
import { PendingImageReviewCard } from './pending-image-review-card';
import { ResultSkeleton } from './skeleton';
import { SearchResultsHeader } from './search-header';

// ── Motion config ─────────────────────────────────────────────────────────────

const motionTransition = {
  type: 'spring',
  bounce: 0,
  duration: 0.3,
} as const;

// ── PendingReviewSection ──────────────────────────────────────────────────────

function PendingReviewSection({ models }: { models: SearchResultItem[] }) {
  if (models.length === 0) return null;

  return (
    <div className="mb-6">
      <p className="text-[11px] font-bold uppercase tracking-widest text-default-500 px-6 mb-1">
        Annotation Review
      </p>
      <div className="flex flex-col">
        {models.map((model) => (
          <PendingReviewCard key={model.id} model={model} />
        ))}
      </div>
      <div className="border-b border-default-200 mx-6 mt-2" />
    </div>
  );
}

// ── PendingImageReviewSection ─────────────────────────────────────────────────

function PendingImageReviewSection({ models }: { models: SearchResultItem[] }) {
  if (models.length === 0) return null;

  return (
    <div className="mb-6">
      <p className="text-[11px] font-bold uppercase tracking-widest text-default-500 px-6 mb-1">
        Image Pending Review
      </p>
      <div className="flex flex-col">
        {models.map((model) => (
          <PendingImageReviewCard key={model.id} model={model} />
        ))}
      </div>
      <div className="border-b border-default-200 mx-6 mt-2" />
    </div>
  );
}

// ── SearchResultsContent ──────────────────────────────────────────────────────

function SearchResultsContent() {
  const { state, data, isLoading, error, refetch } = useSearch();

  if (error) {
    return (
      <ApiErrorDisplay error={error} title="Search failed" onRetry={refetch} />
    );
  }

  const results = data?.results ?? [];

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
        results.map((result) => (
          <SearchResult key={result.id} result={result} />
        ))}
    </motion.div>
  );
}

// ── SearchResultsPagination ───────────────────────────────────────────────────

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

// ── SearchResults (root) ──────────────────────────────────────────────────────

export function SearchResults() {
  const { state, data } = useSearch();

  const isModelTab = state.resourceType === 'model';

  // Determine which status-filtered sections to show based on the active facets.
  // registration_status=pending_review and image_review_status=pending_image_check
  // are set via URL params (e.g. from admin page links); the backend gates the
  // results to the caller's own models automatically.
  const regStatus = state.facets['registration_status'];
  const pendingReviewOn =
    regStatus?.kind === 'terms' && regStatus.values.includes('pending_review');

  const imgStatus = state.facets['image_review_status'];
  const imagePendingReviewOn =
    imgStatus?.kind === 'terms' &&
    imgStatus.values.includes('pending_image_check');

  // When a status filter is active the main search returns exactly those models;
  // render the appropriate branded section instead of the generic result list.
  const results = data?.results ?? [];
  const showPendingSection = isModelTab && pendingReviewOn;
  const showPendingImageSection = isModelTab && imagePendingReviewOn;
  const showMainResults = !showPendingSection && !showPendingImageSection;

  return (
    <div className="flex flex-col w-full grow p-10">
      <SearchResultsHeader />
      {showPendingSection && <PendingReviewSection models={results} />}
      {showPendingImageSection && (
        <PendingImageReviewSection models={results} />
      )}
      {showMainResults && <SearchResultsContent />}
      {showMainResults && <SearchResultsPagination />}
    </div>
  );
}
