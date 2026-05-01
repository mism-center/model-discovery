import { createContext, createElement, useContext } from 'react';
import type { ReactNode } from 'react';

/**
 * Stable per-browser identifier sent as `triggered_by` on run launches.
 *
 * Auth isn't wired up yet, so the server can't tell whose run is whose.
 * Until then we mint a uuid once per browser and persist it to a cookie.
 * The cookie is read on the server out of the request headers and injected
 * into a context, so SSR and the first client render agree on the id and
 * `RunControls` can filter run history without flashing the wrong affordance.
 *
 * When real auth lands, replace callers with the authenticated user id and
 * delete this module.
 */
export const CLIENT_ID_COOKIE = 'mdsc_client_id';
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function mintId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function parseCookieHeader(
  header: string | null,
  name: string
): string | undefined {
  if (!header) return;
  for (const entry of header.split('; ')) {
    const eq = entry.indexOf('=');
    if (eq === -1) continue;
    if (entry.slice(0, eq) === name) {
      return decodeURIComponent(entry.slice(eq + 1));
    }
  }
  return;
}

function buildSetCookie(name: string, value: string): string {
  // SameSite=Lax + Secure is rejected on http://localhost in some browsers,
  // so omit Secure outside production.
  const secure = process.env.NODE_ENV === 'production' ? '; Secure' : '';
  return `${name}=${encodeURIComponent(value)}; Max-Age=${ONE_YEAR_SECONDS}; Path=/; SameSite=Lax${secure}`;
}

/**
 * Read the client id from the request's Cookie header, minting one (and a
 * Set-Cookie response header) if absent. Loaders attach `setCookie` to their
 * response headers so the browser persists a freshly-minted id.
 */
export function resolveClientIdFromRequest(request: Request): {
  clientId: string;
  setCookie?: string;
} {
  const existing = parseCookieHeader(
    request.headers.get('cookie'),
    CLIENT_ID_COOKIE
  );
  if (existing) return { clientId: existing };
  const fresh = mintId();
  return {
    clientId: fresh,
    setCookie: buildSetCookie(CLIENT_ID_COOKIE, fresh),
  };
}

const ClientIdContext = createContext<string | undefined>(undefined);

export function ClientIdProvider({
  value,
  children,
}: {
  value: string;
  children: ReactNode;
}) {
  return createElement(ClientIdContext.Provider, { value }, children);
}

export function useClientId(): string | undefined {
  return useContext(ClientIdContext);
}
