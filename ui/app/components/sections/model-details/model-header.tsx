import cn from 'classnames';
import { BreadcrumbItem, Button } from '@heroui/react';
import { ArrowRightEndOnRectangleIcon } from '@heroicons/react/16/solid';
import { useLocation } from 'react-router';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { loginHref, useUser } from '~/api/auth/user';
import { CompactBreadcrumbs } from '~/components/layout/breadcrumbs';
import { RunControls } from '~/components/sections/search/search-results/run-controls';
import { ModelByline } from './model-byline';
import { Chip, OVERVIEW_TITLE, hasItems, sectionId } from './primitives';

/**
 * Sign-in affordance for an anonymous visitor looking at an executable model.
 *
 * `RunControls` renders nothing without a user, so an anonymous visitor would
 * otherwise see an "Executable" badge with no way to act on it. Renders nothing
 * while the user query is in flight so the button doesn't flash for signed-in
 * users on first paint. Sizing tracks `RunControls`' `page` scale so the two
 * variants of this slot are interchangeable.
 *
 * `loginHref()` returns the user here: `/models/:id` is a parameterized return-to
 * route, so the client sends the route key plus the id and the server rebuilds
 * the path from its own template after validating the id as a UUID.
 */
function SignInToRunPrompt({ executable }: { executable: boolean }) {
  const { user, isLoading } = useUser();
  const { pathname, search } = useLocation();
  if (!executable || isLoading || user) return null;

  // Filled, not bordered, and identical in size and padding to `RunControls`'
  // `page` scale: this stands in for that button, so it should carry the same
  // weight rather than looking like a lesser version of it. An outline next to
  // nothing reads as unfinished, and for an anonymous visitor this *is* the
  // page's primary action.
  //
  // No caption underneath either — "Running a model requires an account" only
  // restated the label, and stacking it turned one control into a two-line block.
  return (
    <Button
      as="a"
      href={loginHref(pathname, search)}
      size="md"
      color="primary"
      className="px-6 rounded-lg text-[15px] font-bold"
      startContent={<ArrowRightEndOnRectangleIcon className="size-4" />}
    >
      Sign in to run
    </Button>
  );
}

/**
 * Breadcrumbs are a single line above a title that already shows the name in
 * full, so an unreasonably long name is truncated here rather than wrapping the
 * trail onto three lines. The limit is deliberately generous — ordinary model
 * names pass through untouched.
 */
const BREADCRUMB_MAX = 72;

function truncateBreadcrumb(name: string): string {
  if (name.length <= BREADCRUMB_MAX) return name;
  return `${name.slice(0, BREADCRUMB_MAX - 1).trimEnd()}…`;
}

/**
 * Page header: breadcrumbs, executable badge, title, byline, description, tags,
 * and the primary launch action (or a sign-in prompt when anonymous).
 *
 * The action scrolls away with the header. A sticky bar and a rail button were
 * both tried; each fixed reachability but cost more than it bought — the bar left
 * a dead band under the header unpinned, and moved the button between states.
 */
export function ModelHeader({ model }: { model: ModelDetailResponse }) {
  const executable = Boolean(model.execution_type);
  const description = model.description || model.short_description;
  const shortName = truncateBreadcrumb(model.name);

  return (
    // `scroll-mt-20` matches SectionCard, so every nav anchor lands alike.
    <header
      id={sectionId(OVERVIEW_TITLE)}
      className="scroll-mt-20 flex flex-col gap-4"
    >
      <CompactBreadcrumbs>
        <BreadcrumbItem href="/">Home</BreadcrumbItem>
        <BreadcrumbItem href="/search">Search</BreadcrumbItem>
        <BreadcrumbItem>
          {shortName === model.name ? (
            model.name
          ) : (
            <span title={model.name}>{shortName}</span>
          )}
        </BreadcrumbItem>
      </CompactBreadcrumbs>

      {/* Stacks below sm: a text-3xl title and the launch button cannot share a
          375px row without crushing the title. */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 sm:gap-6">
        <div className="min-w-0">
          {executable && (
            <span
              className={cn(
                'inline-flex items-center px-2 py-0.5 mb-2',
                'rounded-xs bg-primary',
                'text-white text-xs font-bold uppercase tracking-wide'
              )}
            >
              Executable
            </span>
          )}
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            {model.name}
          </h1>
          <ModelByline model={model} />
          {description && (
            <p className="mt-3 text-base text-default-900 leading-relaxed max-w-3xl">
              {description}
            </p>
          )}
          {/* `hasItems`, not `.length` — the API emits `[]` rather than omitting
              these, and `0 || 0` renders a literal "0". */}
          {(hasItems(model.model_scales) || hasItems(model.domains)) && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {model.model_scales?.map((s) => (
                <Chip key={s} facet="model_scales">
                  {s}
                </Chip>
              ))}
              {model.domains?.map((d) => (
                <Chip key={d} facet="domains">
                  {d}
                </Chip>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1.5 shrink-0">
          <SignInToRunPrompt executable={executable} />
          <RunControls model={model} scale="page" />
        </div>
      </div>
    </header>
  );
}
