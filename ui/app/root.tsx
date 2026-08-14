import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useHref,
  useNavigate,
  useRouteLoaderData,
} from 'react-router';
import { HeroUIProvider, ToastProvider } from '@heroui/react';
import {
  HydrationBoundary,
  QueryClientProvider,
  dehydrate,
  type DehydratedState,
} from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import type { Route } from './+types/root';
import { Header } from './components/layout/header';
import { AuthErrorBanner } from './components/layout/auth-error-banner';
import { NavigationProgress } from './components/layout/navigation-progress';
import { prefetchUser } from './api/auth/user';
import { serverApiClient } from './api/client/server-client';
import { getQueryClient } from './api/query/query-client';
import './styles/index.css';

export function meta() {
  return [
    // TODO
    { title: 'Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content: 'Multiscale Immune Systems Modeling - Multiscale Model Portal',
    },
  ];
}

export function links() {
  return [
    {
      rel: 'icon',
      type: 'image/svg+xml',
      href: '/favicon.svg',
    },
  ];
}

/**
 * Prefetch the current user on the server so the first paint matches the
 * client-side hydration. Forwards the inbound cookie to the API via
 * `serverApiClient` — without that, `apiClient`'s `credentials: 'include'`
 * has no cookie jar to draw from in Node.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const queryClient = getQueryClient();
  // The only place the user is prefetched. This boundary wraps the whole route
  // tree, so every route inherits the hydrated user without prefetching it again.
  await prefetchUser(queryClient, serverApiClient(request), request);
  return { dehydratedState: dehydrate(queryClient) };
}

function Providers({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const queryClient = getQueryClient();
  // Hydrate at the layout level so global chrome (Header, AuthErrorBanner)
  // sees the SSR-prefetched user cache instead of cold-fetching after mount.
  const rootData = useRouteLoaderData('root') as
    | { dehydratedState?: DehydratedState }
    | undefined;
  return (
    <QueryClientProvider client={queryClient}>
      <HydrationBoundary state={rootData?.dehydratedState}>
        <HeroUIProvider
          // HeroUI's provider creates a div container
          className="min-h-dvh"
          navigate={navigate}
          useHref={useHref}
        >
          <ToastProvider placement="bottom-right" toastOffset={12} />
          {children}
        </HeroUIProvider>
        {import.meta.env.DEV && (
          <ReactQueryDevtools
            initialIsOpen={false}
            buttonPosition="bottom-left"
          />
        )}
      </HydrationBoundary>
    </QueryClientProvider>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="light" data-theme="light">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body className="min-h-dvh">
        <Providers>
          {/* Outside the column so it can pin itself over the sticky header. */}
          <NavigationProgress />
          <div className="min-h-dvh flex flex-col grow">
            <Header />
            <AuthErrorBanner />
            {children}
          </div>
          {/* <Footer /> */}
          <ScrollRestoration />
          <Scripts />
        </Providers>
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  let message = 'Oops!';
  let details = 'An unexpected error occurred.';
  let stack: string | undefined;

  if (isRouteErrorResponse(error)) {
    message = error.status === 404 ? '404' : 'Error';
    details =
      error.status === 404
        ? 'The requested page could not be found.'
        : error.statusText || details;
  } else if (import.meta.env.DEV && error && error instanceof Error) {
    details = error.message;
    stack = error.stack;
  }

  return (
    <main className="pt-16 p-4 container mx-auto">
      <h1>{message}</h1>
      <p>{details}</p>
      {stack && (
        <pre className="w-full p-4 overflow-x-auto">
          <code>{stack}</code>
        </pre>
      )}
    </main>
  );
}
