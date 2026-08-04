import { useQuery } from '@tanstack/react-query';

import { ApiError } from '~/api';
import type { ModelDetailResponse } from '~/api/endpoints/models';
import { modelDetailQueryOptions } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { ExecutionSection } from './execution-section';
import { FilesSection } from './files-section';
import { IOSpecSection } from './io-spec-section';
import { MetadataSidebar } from './metadata-sidebar';
import { ModelHeader } from './model-header';
import { sectionId } from './primitives';
import { RunHistorySection } from './run-history-section';
import { SectionNav, type SectionLink } from './section-nav';
import { ModelDetailsSkeleton } from './skeleton';

/**
 * Sections in reading order, and the source of truth for the nav rail.
 *
 * Fixed, not derived from which fields happen to be populated: the nav must not
 * change shape per model, and a section that has nothing to show says so rather
 * than disappearing.
 */
const SECTION_TITLES = [
  'Inputs & outputs',
  'Model characterization',
  'Execution',
  'Biology',
  'Provenance',
  'Files',
  'Run history',
] as const;

const SECTIONS: SectionLink[] = SECTION_TITLES.map((title) => ({
  id: sectionId(title),
  label: title,
}));

/**
 * Model details page.
 *
 * Uses the app's established shell — full-bleed `[rail | white pane]` grid on a
 * `bg-default-50` gutter, content at `p-10` — the same structure as
 * `routes/search.tsx` and `my-runs.tsx`. The first pass invented a centered
 * `max-w-6xl` cards-on-gray layout with a right-hand rail, which made this the
 * only page in the app built that way.
 */
export function ModelDetailsSection({ modelId }: { modelId: string }) {
  const {
    data: model,
    isLoading,
    error,
    refetch,
  } = useQuery(modelDetailQueryOptions(modelId));

  return (
    <main className="flex flex-col grow">
      <div className="grid grid-cols-1 lg:grid-cols-[auto_minmax(0,1fr)] grow bg-default-50">
        {/*
         * The rail is hidden until lg, matching SectionNav's own breakpoint. It
         * keeps its width while loading so the content pane doesn't jump when
         * the nav appears, but it lists nothing when there are no sections to
         * navigate — a not-found page advertising seven anchors is a lie.
         */}
        <div className="hidden lg:block lg:min-w-[280px]">
          {model && !error && <SectionNav sections={SECTIONS} />}
        </div>
        <section className="col-start-1 lg:col-start-2 lg:border-l border-slate-200 bg-white">
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
  return (
    <div className="flex flex-col gap-8">
      <ModelHeader model={model} />
      <IOSpecSection model={model} />
      <ExecutionSection model={model} />
      <MetadataSidebar model={model} />
      <FilesSection modelId={modelId} />
      <RunHistorySection modelId={modelId} />
    </div>
  );
}
