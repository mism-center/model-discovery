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
 * Whether this request will produce an HTML document rather than route data.
 *
 * React Router serves both from the same loader: a document request on first
 * load, and a `/models/:id.data` fetch on every client-side navigation.
 * `Sec-Fetch-Mode` distinguishes them — `navigate` for a document, `cors`
 * for the data fetch.
 *
 * Absent header means a client that doesn't send `Sec-Fetch-*` (a crawler, curl,
 * a proxy that strips it). Those are document consumers, and the fallback should
 * favour a complete page over a fast one, so treat unknown as a document.
 */
function isDocumentRequest(request: Request): boolean {
  return request.headers.get('sec-fetch-mode') !== 'cors';
}

/**
 * Prefetch what the response actually needs, which is not the same for the two
 * kinds of request this loader serves.
 *
 * Mirrors search.tsx: swallow prefetch errors so a transient backend hiccup
 * renders the in-page error state (ApiErrorDisplay) rather than 500'ing the route
 * — the client `useQuery` re-runs and surfaces the failure.
 *
 * The model is always awaited. `meta()` needs its name for an SSR title (it runs
 * before the client query resolves, so it can't read the cache) and the status
 * code decision below needs to know whether the id exists.
 *
 * The file listing and — for signed-in visitors — this model's runs are awaited
 * only for a **document** request. A fully-rendered first paint is worth paying
 * for; a client navigation is not, because React Router blocks the transition
 * until this resolves, so everything awaited here is time the *previous* page
 * sits on screen looking idle, and a `Promise.all` pays for its slowest member.
 * On the client path `FilesSection` and `RunHistorySection` each own their query
 * and render a skeleton while it is in flight, so they fill in a moment after the
 * page arrives instead of holding it back; on the document path they arrive already
 * populated.
 *
 * This route is public, so it must not use `requireUser` — that redirects
 * anonymous visitors, and only the run-history *section* is gated, not the page.
 */
export async function loader({ params, request }: Route.LoaderArgs) {
  const modelId = params.id;
  const client = serverApiClient(request);
  const queryClient = getQueryClient();

  const modelQuery = modelDetailQueryOptions(modelId, client);

  // `GET /models/:id/runs` is scoped to the caller and 401s without a session,
  // so prefetching it for an anonymous visitor is a guaranteed failure whose
  // only effect is an error state.
  //
  // `resolveUser` rather than `prefetchUser`: this needs the value to make a
  // decision, not a copy of the user in this route's dehydrated payload — root
  // already hydrates that. It also shares root's `/api/auth/me` round-trip for
  // this request. Chained rather than awaited up front so it overlaps the model
  // and file prefetches instead of serialising ahead of them.
  const documentExtras = isDocumentRequest(request)
    ? [
        queryClient.prefetchQuery(resourceFilesQueryOptions(modelId, client)),
        resolveUser(request, client).then((user) =>
          user
            ? queryClient.prefetchQuery(modelRunsQueryOptions(modelId, client))
            : undefined
        ),
      ]
    : [];

  await Promise.all([queryClient.prefetchQuery(modelQuery), ...documentExtras]);

  const modelName = queryClient.getQueryData<{ name?: string }>(
    modelQuery.queryKey
  )?.name;

  // `prefetchQuery` never rejects — it swallows the failure and records it on the
  // query instead — so awaiting it cannot observe a 404. Read the error the query
  // recorded to decide whether this id exists.
  const prefetchError = queryClient.getQueryState(modelQuery.queryKey)?.error;

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
