import { motion } from 'framer-motion';
import { Pagination } from '@heroui/react';
import { useQuery } from '@tanstack/react-query';
import { useSearch } from '~/search/context/search-context';
import { useUser } from '~/api/auth/user';
import {
  pendingReviewModelsQueryOptions,
  pendingImageReviewModelsQueryOptions,
} from '~/api/query/models';
import type { ModelListItem } from '~/api/endpoints/models';
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

function PendingReviewSection({ models }: { models: ModelListItem[] }) {
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

function PendingImageReviewSection({
  models,
  userId,
}: {
  models: ModelListItem[];
  userId: string;
}) {
  if (models.length === 0) return null;

  return (
    <div className="mb-6">
      <p className="text-[11px] font-bold uppercase tracking-widest text-default-500 px-6 mb-1">
        Image Pending Review
      </p>
      <div className="flex flex-col">
        {models.map((model) => (
          <PendingImageReviewCard
            key={model.id}
            model={model}
            userId={userId}
          />
        ))}
      </div>
      <div className="border-b border-default-200 mx-6 mt-2" />
    </div>
  );
}

// ── SearchResultsContent ──────────────────────────────────────────────────────

function SearchResultsContent({
  filterExecutable,
}: {
  filterExecutable: boolean;
}) {
  const { state, data, isLoading, error, refetch } = useSearch();

  if (error) {
    return (
      <ApiErrorDisplay error={error} title="Search failed" onRetry={refetch} />
    );
  }

  const results = filterExecutable
    ? (data?.results ?? []).filter((r) => Boolean(r.execution_type))
    : (data?.results ?? []);

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
      {!isLoading && filterExecutable && results.length === 0 && (
        <p className="text-sm text-default-500 px-6 py-4">
          No executable models found.
        </p>
      )}
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
  const { state, getFacet } = useSearch();
  const { user } = useUser();

  const userId = user?.sub ?? '';

  const { data: pendingReviewData } = useQuery({
    ...pendingReviewModelsQueryOptions(),
    enabled: !!user,
  });

  const { data: pendingImageReviewData } = useQuery({
    ...pendingImageReviewModelsQueryOptions(userId),
    enabled: !!user,
  });

  const pendingModels = pendingReviewData?.results ?? [];
  const hasPendingModels = pendingModels.length > 0;
  const pendingImageModels = pendingImageReviewData?.results ?? [];
  const hasPendingImageModels = pendingImageModels.length > 0;
  const isModelTab = state.resourceType === 'model';

  const modelStatus = getFacet('model_status');
  const selectedStatuses =
    modelStatus?.kind === 'terms' ? modelStatus.values : [];
  const pendingReviewOn = selectedStatuses.includes('annotation_review');
  const executableOn = selectedStatuses.includes('executable');
  const imagePendingReviewOn = selectedStatuses.includes(
    'image_pending_review'
  );
  const anyFilterOn = pendingReviewOn || executableOn || imagePendingReviewOn;

  const showPendingSection =
    isModelTab && hasPendingModels && (!anyFilterOn || pendingReviewOn);
  const showPendingImageSection =
    isModelTab &&
    hasPendingImageModels &&
    (!anyFilterOn || imagePendingReviewOn);
  const showMainResults = !anyFilterOn || executableOn;
  const filterToExecutable = isModelTab && executableOn;

  return (
    <div className="flex flex-col w-full grow p-10">
      <SearchResultsHeader />
      {showPendingSection && <PendingReviewSection models={pendingModels} />}
      {showPendingImageSection && (
        <PendingImageReviewSection
          models={pendingImageModels}
          userId={userId}
        />
      )}
      {showMainResults && (
        <SearchResultsContent filterExecutable={filterToExecutable} />
      )}
      {showMainResults && !filterToExecutable && <SearchResultsPagination />}
    </div>
  );
}
