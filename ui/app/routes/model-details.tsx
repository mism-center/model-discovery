import { HydrationBoundary, dehydrate } from '@tanstack/react-query';
import { data } from 'react-router';
import type { ShouldRevalidateFunctionArgs } from 'react-router';

import { ApiError } from '~/api';
import { resolveUser } from '~/api/auth/user';
import { serverApiClient } from '~/api/client/server-client';
import { getQueryClient } from '~/api/query/query-client';
import { modelDetailQueryOptions } from '~/api/query/models';
import { modelRunsQueryOptions } from '~/api/query/runs';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { ModelDetailsSection } from '~/components/sections/model-details/model-details';
import type { Route } from './+types/model-details';

export function meta({ data }: Route.MetaArgs) {
  const name = data?.modelName;
  // A wrong id is the likeliest way to land here, and titling that page
  // "Model | Multiscale Model Portal" claims a model exists. The response is
  // still HTTP 200 — making it a real 404 means throwing from the loader and
  // teaching the root ErrorBoundary to render a not-found page, which is a
  // separate change.
  let title = 'Model | Multiscale Model Portal | MISM';
  if (data?.notFound) title = 'Model not found | MISM';
  else if (name) title = `${name} | Model | MISM`;
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
 * Prefetch the model, its file listing, and — for signed-in visitors only — the
 * caller's runs, so the first paint has data. Mirrors search.tsx: swallow
 * prefetch errors so a transient backend hiccup renders the in-page error state
 * (ApiErrorDisplay) rather than 500'ing the route — the client `useQuery` re-runs
 * and surfaces the failure.
 *
 * The model name is fetched (best-effort) so `meta()` can render an SSR title;
 * `meta()` runs before the client query resolves, so it can't read the cache.
 *
 * This route is public, so it must not use `requireUser` — that redirects
 * anonymous visitors, and only the run-history *section* is gated, not the page.
 */
export async function loader({ params, request }: Route.LoaderArgs) {
  const modelId = params.id;
  const client = serverApiClient(request);
  const queryClient = getQueryClient();

  // `GET /models/:id/runs` is scoped to the caller and 401s without a session,
  // so prefetching it for an anonymous visitor is a guaranteed failure whose
  // only effect is an error state.
  //
  // `resolveUser` rather than `prefetchUser`: this needs the value to make a
  // decision, not a copy of the user in this route's dehydrated payload — root
  // already hydrates that. It also shares root's `/api/auth/me` round-trip for
  // this request. Chained rather than awaited up front so the model and file
  // prefetches still run concurrently with the auth check.
  const runsPrefetch = resolveUser(request, client).then((user) => {
    if (!user) return;
    return queryClient.prefetchQuery(modelRunsQueryOptions(modelId, client));
  });

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
    queryClient.prefetchQuery(resourceFilesQueryOptions(modelId, client)),
    runsPrefetch,
  ]);

  // `prefetchQuery` never rejects — it swallows the failure and records it on the
  // query instead — so the `.catch` above cannot observe a 404. Read the error the
  // query recorded to decide whether this id exists.
  const prefetchError = queryClient.getQueryState(
    modelDetailQueryOptions(modelId, client).queryKey
  )?.error;

  const notFound =
    prefetchError instanceof ApiError && prefetchError.status === 404;

  // `data()` sets the response status without throwing, so a missing model
  // answers a real HTTP 404 to crawlers and monitoring while still rendering the
  // styled in-page "Model not found" state (throwing would hand the whole route
  // to the root ErrorBoundary and lose both the layout and the title).
  return data(
    { dehydratedState: dehydrate(queryClient), modelId, modelName, notFound },
    { status: notFound ? 404 : 200 }
  );
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
