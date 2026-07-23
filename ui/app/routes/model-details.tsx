import { HydrationBoundary, dehydrate } from '@tanstack/react-query';
import type { ShouldRevalidateFunctionArgs } from 'react-router';

import { prefetchUser } from '~/api/auth/user';
import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';
import { modelDetailQueryOptions } from '~/api/query/models';
import { modelRunsQueryOptions } from '~/api/query/runs';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { ModelDetailsSection } from '~/components/sections/model-details/model-details';
import type { Route } from './+types/model-details';

export function meta({ data }: Route.MetaArgs) {
  const name = data?.modelName;
  const title = name
    ? `${name} | Model | MISM`
    : 'Model | Multiscale Model Portal | MISM';
  return [
    { title },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Model details',
    },
  ];
}

/**
 * Prefetch the model, its run history, and its file listing on the server so
 * the first paint has data. Mirrors search.tsx: swallow prefetch errors so a
 * transient backend hiccup renders the in-page error state (ApiErrorDisplay)
 * rather than 500'ing the route — the client `useQuery` re-runs and surfaces
 * the failure.
 *
 * The model name is fetched (best-effort) so `meta()` can render an SSR title;
 * `meta()` runs before the client query resolves, so it can't read the cache.
 */
export async function loader({ params, request }: Route.LoaderArgs) {
  const modelId = params.id;
  const client = serverApiClient(request);
  const queryClient = getQueryClient();

  let modelName: string | undefined;
  await Promise.all([
    queryClient
      .prefetchQuery(modelDetailQueryOptions(modelId, client))
      .then(() => {
        modelName = queryClient.getQueryData<{ name?: string }>(
          modelDetailQueryOptions(modelId, client).queryKey
        )?.name;
      })
      .catch(() => {}),
    queryClient.prefetchQuery(modelRunsQueryOptions(modelId, client)),
    queryClient.prefetchQuery(resourceFilesQueryOptions(modelId)),
    prefetchUser(queryClient, client),
  ]);

  return { dehydratedState: dehydrate(queryClient), modelId, modelName };
}

/**
 * Skip the loader for same-path navigations; React Query owns refetching once
 * hydrated. Revalidate across pathname changes and explicit revalidation.
 */
export function shouldRevalidate({
  currentUrl,
  nextUrl,
  defaultShouldRevalidate,
}: ShouldRevalidateFunctionArgs) {
  if (currentUrl.pathname === nextUrl.pathname) return false;
  return defaultShouldRevalidate;
}

export default function ModelDetails({ loaderData }: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <ModelDetailsSection modelId={loaderData.modelId} />
    </HydrationBoundary>
  );
}
