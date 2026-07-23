import cn from 'classnames';
import { BreadcrumbItem } from '@heroui/react';

import type { ModelDetailResponse } from '~/api/endpoints/models';
import { CompactBreadcrumbs } from '~/components/layout/breadcrumbs';
import { RunControls } from '~/components/sections/search/search-results/run-controls';
import { Chip } from './primitives';

/**
 * Compact page header: breadcrumbs, executable badge, title, description, and
 * the primary launch action. Mirrors the light-background header used on the
 * runs page.
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
                'text-white text-[10px] font-bold uppercase tracking-wide'
              )}
            >
              Executable
            </span>
          )}
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            {model.name}
          </h1>
          {description && (
            <p className="mt-3 text-[15px] text-default-800/90 leading-relaxed max-w-3xl">
              {description}
            </p>
          )}
          {(model.model_scales?.length || model.domains?.length) && (
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
          <RunControls model={model} />
        </div>
      </div>
    </header>
  );
}
