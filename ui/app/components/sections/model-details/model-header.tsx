import cn from 'classnames';
import { BreadcrumbItem, Button } from '@heroui/react';
import { ArrowRightEndOnRectangleIcon } from '@heroicons/react/16/solid';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { signIn, useUser } from '~/api/auth/user';
import { CompactBreadcrumbs } from '~/components/layout/breadcrumbs';
import { RunControls } from '~/components/sections/search/search-results/run-controls';
import { Chip } from './primitives';

function hasItems(values: string[] | null | undefined): boolean {
  return Array.isArray(values) && values.length > 0;
}

/**
 * Sign-in affordance for an anonymous visitor looking at an executable model.
 *
 * `RunControls` renders nothing when there is no user, so the page used to show
 * an "Executable" badge and no way to act on it — the badge made a promise the
 * page then refused to explain. This states the requirement instead.
 *
 * Renders nothing while the user query is in flight, so the button doesn't flash
 * for signed-in users on first paint.
 *
 * `signIn()` returns the user to this page: `/models/:id` is registered as a
 * parameterized return-to route, so the client sends the route key plus the id
 * as data and the server rebuilds the path from its own template after
 * validating the id as a UUID.
 */
function SignInToRunPrompt({ executable }: { executable: boolean }) {
  const { user, isLoading } = useUser();
  if (!executable || isLoading || user) return null;

  return (
    <div className="flex flex-col items-end gap-1.5">
      <Button
        size="lg"
        color="primary"
        variant="bordered"
        className="px-6 rounded-lg text-base font-bold"
        startContent={<ArrowRightEndOnRectangleIcon className="size-4" />}
        onPress={() => signIn()}
      >
        Sign in to run
      </Button>
      <p className="text-xs text-default-800">
        Running a model requires an account.
      </p>
    </div>
  );
}

/**
 * Page header: breadcrumbs, executable badge, title, description, tags, and the
 * primary launch action (or a sign-in prompt when anonymous).
 *
 * Sits at the top of the content pane, above the anchored sections.
 */
export function ModelHeader({ model }: { model: ModelDetailResponse }) {
  const executable = Boolean(model.execution_type);
  const description = model.description || model.short_description;

  return (
    <header className="flex flex-col gap-4">
      <CompactBreadcrumbs>
        <BreadcrumbItem href="/">Home</BreadcrumbItem>
        <BreadcrumbItem href="/search">Search</BreadcrumbItem>
        <BreadcrumbItem>{model.name}</BreadcrumbItem>
      </CompactBreadcrumbs>

      <div className="flex items-start justify-between gap-6">
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
          {description && (
            <p className="mt-3 text-base text-default-900 leading-relaxed max-w-3xl">
              {description}
            </p>
          )}
          {/*
           * `.length > 0`, not `.length` — the API always emits these as `[]`
           * rather than omitting them, so `0 || 0` evaluated to `0` and React
           * rendered a literal "0" in the header of every model that had no
           * scales and no domains, which is most of them.
           */}
          {(hasItems(model.model_scales) || hasItems(model.domains)) && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {model.model_scales?.map((s) => (
                <Chip key={s} tone="primary">
                  {s}
                </Chip>
              ))}
              {model.domains?.map((d) => (
                <Chip key={d} tone="neutral">
                  {d}
                </Chip>
              ))}
            </div>
          )}
        </div>

        <div className="shrink-0">
          <SignInToRunPrompt executable={executable} />
          <RunControls model={model} scale="page" />
        </div>
      </div>
    </header>
  );
}
