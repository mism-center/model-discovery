import cn from 'classnames';
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '~/api';
import { useUser } from '~/api/auth/user';
import type { ModelDetailResponse } from '~/api/endpoints/models';
import { modelDetailQueryOptions } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { BackToTop } from '~/components/common/back-to-top';
import { BiologySection } from './biology-section';
import { ExecutionSection, executionSubsections } from './execution-section';
import { FilesSection } from './files-section';
import { IOSpecSection, ioSectionSubsections } from './io-spec-section';
import { ModelCharacterizationSection } from './model-characterization-section';
import { ModelHeader } from './model-header';
import { OVERVIEW_TITLE, sectionId, type Subsection } from './primitives';
import { ProvenanceSection } from './provenance-section';
import { RunHistorySection } from './run-history-section';
import { SectionCollapseProvider } from './section-collapse';
import { SectionNav, type SectionLink } from './section-nav';
import { ModelDetailsSkeleton, SectionNavSkeleton } from './skeleton';

/**
 * Sections in reading order, and the source of truth for the nav rail.
 *
 * Ordered by the question each one answers, not by which fields ingestion
 * happens to populate — otherwise the page's shape would track data gaps rather
 * than what a reader needs:
 *
 *   what is this      → Overview, Model characterization, Biology
 *   what does it take → Inputs & outputs
 *   how do I run it   → Execution, Files, Run history
 *   who made it       → Provenance
 *
 * Characterization leads the titled sections because it orients everything below
 * it. Biology follows it directly: the two are the same question (the
 * mathematics, and what the mathematics is about), so an operational section must
 * not split them. Provenance is reference material, so it trails.
 *
 * Not derived from which fields are populated: the nav must not change shape per
 * model, and a section with nothing to show says so rather than disappearing.
 *
 * `requiresUser` is the one exception, and it is a different axis. Run history is
 * scoped to the caller by `GET /models/:id/runs`, so for an anonymous visitor it
 * is not data that happens to be missing — it is data that cannot exist. Showing
 * a sign-in prompt mid-page would be noise the header's "Sign in to run" already
 * covers, and listing a nav anchor that leads to it would be a dead end. Varying
 * by viewer does not reintroduce the problem the fixed list solves, which was
 * the page changing shape from one model to the next.
 */
const SECTION_DEFS = [
  { title: OVERVIEW_TITLE },
  { title: 'Model characterization' },
  { title: 'Biology' },
  { title: 'Inputs & outputs' },
  { title: 'Execution' },
  { title: 'Files' },
  { title: 'Run history', requiresUser: true },
  { title: 'Provenance' },
] as const;

/**
 * Subsection entries per section, keyed by section id.
 *
 * Only the two long sections have subheadings worth navigating; the rest are flat
 * field grids. Each source function lives beside the component that renders those
 * subheadings and is derived from the same block list, so the nav cannot offer an
 * anchor the page did not render.
 *
 * Empty until the model loads, which is also when the nav is still a skeleton.
 */
function subsectionsFor(
  model: ModelDetailResponse | undefined
): Record<string, Subsection[]> {
  if (!model) return {};
  return {
    [sectionId('Inputs & outputs')]: ioSectionSubsections(model),
    [sectionId('Execution')]: executionSubsections(model),
  };
}

function sectionsFor(
  hasUser: boolean,
  model: ModelDetailResponse | undefined
): SectionLink[] {
  const subsections = subsectionsFor(model);
  return SECTION_DEFS.filter(
    (section) => !('requiresUser' in section) || hasUser
  ).map(({ title }) => {
    const id = sectionId(title);
    return { id, label: title, children: subsections[id] };
  });
}

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

  // One source of truth for the auth-gated section, so the nav and the body
  // cannot disagree and leave an anchor pointing at nothing. `isLoading` counts
  // as "no user" only until the session resolves — it is hydrated from the
  // loader, so in practice it is known on first paint.
  const { user } = useUser();
  const sections = sectionsFor(Boolean(user), model);

  // The rail exists to navigate sections, so it has nothing to offer when the
  // model failed to load. Collapsing to one column beats leaving a 280px empty
  // gutter beside a "not found" message, which just reads as broken layout.
  const showRail = !error;

  return (
    // Spans rail and pane both, since the nav re-opens sections it jumps to.
    <SectionCollapseProvider>
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
            <div className="hidden lg:block lg:min-w-70">
              {model ? (
                <SectionNav sections={sections} />
              ) : (
                <SectionNavSkeleton items={sections.length} />
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
                showRunHistory={Boolean(user)}
              />
            </div>
          </section>
        </div>
        <BackToTop />
      </main>
    </SectionCollapseProvider>
  );
}

function Body({
  modelId,
  model,
  isLoading,
  error,
  refetch,
  showRunHistory,
}: {
  modelId: string;
  model: ModelDetailResponse | undefined;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
  showRunHistory: boolean;
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
      {showRunHistory && <RunHistorySection modelId={modelId} />}
      <ProvenanceSection model={model} />
    </div>
  );
}
