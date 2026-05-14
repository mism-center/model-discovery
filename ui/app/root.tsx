import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useHref,
  useNavigate,
} from 'react-router';
import { HeroUIProvider } from '@heroui/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import type { Route } from './+types/root';
import { Header } from './components/layout/header';
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

function Providers({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const queryClient = getQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <HeroUIProvider
        // HeroUI's provider creates a div container
        className="min-h-dvh"
        navigate={navigate}
        useHref={useHref}
      >
        {children}
      </HeroUIProvider>
      {import.meta.env.DEV && (
        <ReactQueryDevtools
          initialIsOpen={false}
          buttonPosition="bottom-left"
        />
      )}
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
          <div className="min-h-dvh flex flex-col grow">
            <Header />
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
