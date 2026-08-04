import cn from 'classnames';
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '~/api';
import type { ModelDetailResponse } from '~/api/endpoints/models';
import { modelDetailQueryOptions } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { BackToTop } from '~/components/common/back-to-top';
import { BiologySection } from './biology-section';
import { ExecutionSection } from './execution-section';
import { FilesSection } from './files-section';
import { IOSpecSection } from './io-spec-section';
import { ModelCharacterizationSection } from './model-characterization-section';
import { ModelHeader } from './model-header';
import { sectionId } from './primitives';
import { ProvenanceSection } from './provenance-section';
import { RunHistorySection } from './run-history-section';
import { SectionNav, type SectionLink } from './section-nav';
import { ModelDetailsSkeleton, SectionNavSkeleton } from './skeleton';

/**
 * Sections in reading order, and the source of truth for the nav rail.
 *
 * Ordered by the question each one answers, not by which fields ingestion
 * happens to populate — otherwise the page's shape would track data gaps rather
 * than what a reader needs:
 *
 *   what is this      → Model characterization, Biology
 *   what does it take → Inputs & outputs
 *   how do I run it   → Execution, Files, Run history
 *   who made it       → Provenance
 *
 * Characterization leads because it orients everything below it. Biology follows
 * it directly: the two are the same question (the mathematics, and what the
 * mathematics is about), so an operational section must not split them.
 * Provenance is reference material, so it trails.
 *
 * Fixed, not derived from which fields are populated: the nav must not change
 * shape per model, and a section that has nothing to show says so rather than
 * disappearing.
 */
const SECTION_TITLES = [
  'Model characterization',
  'Biology',
  'Inputs & outputs',
  'Execution',
  'Files',
  'Run history',
  'Provenance',
] as const;

const SECTIONS: SectionLink[] = SECTION_TITLES.map((title) => ({
  id: sectionId(title),
  label: title,
}));

/**
 * Model details page.
 *
 * Uses the app's established shell — full-bleed `[rail | white pane]` grid on a
 * `bg-default-50` gutter — the same structure as `search.tsx` and `my-runs.tsx`,
 * with the rail collapsing below `lg`.
 */
export function ModelDetailsSection({ modelId }: { modelId: string }) {
  const {
    data: model,
    isLoading,
    error,
    refetch,
  } = useQuery(modelDetailQueryOptions(modelId));

  // The rail exists to navigate sections, so it has nothing to offer when the
  // model failed to load. Collapsing to one column beats leaving a 280px empty
  // gutter beside a "not found" message, which just reads as broken layout.
  const showRail = !error;

  return (
    <main className="flex flex-col grow">
      <div
        className={cn(
          'grid grow bg-default-50',
          showRail
            ? 'grid-cols-1 lg:grid-cols-[auto_minmax(0,1fr)]'
            : 'grid-cols-1'
        )}
      >
        {showRail && (
          <div className="hidden lg:block lg:min-w-[280px]">
            {model ? (
              <SectionNav sections={SECTIONS} />
            ) : (
              <SectionNavSkeleton items={SECTIONS.length} />
            )}
          </div>
        )}
        <section
          className={cn(
            'bg-white border-slate-200',
            showRail && 'lg:col-start-2 lg:border-l'
          )}
        >
          <div className="p-6 lg:p-10">
            <Body
              modelId={modelId}
              model={model}
              isLoading={isLoading}
              error={error}
              refetch={refetch}
            />
          </div>
        </section>
      </div>
      <BackToTop />
    </main>
  );
}

function Body({
  modelId,
  model,
  isLoading,
  error,
  refetch,
}: {
  modelId: string;
  model: ModelDetailResponse | undefined;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}) {
  if (error) {
    // A missing id is the most likely failure on this route, and it is not
    // retryable — offering "Try again" on a 404 just invites the user to fail
    // twice. Route them back to search instead.
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <ApiErrorDisplay
        error={error}
        title={notFound ? 'Model not found' : "Couldn't load this model"}
        onRetry={notFound ? undefined : refetch}
      />
    );
  }
  if (isLoading || !model) {
    return <ModelDetailsSkeleton />;
  }
  // Order must match SECTION_TITLES — the nav's scroll-spy assumes DOM order.
  return (
    <div className="flex flex-col gap-8">
      <ModelHeader model={model} />
      <ModelCharacterizationSection model={model} />
      <BiologySection model={model} />
      <IOSpecSection model={model} />
      <ExecutionSection model={model} />
      <FilesSection modelId={modelId} />
      <RunHistorySection modelId={modelId} />
      <ProvenanceSection model={model} />
    </div>
  );
}
