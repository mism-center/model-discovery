import createClient from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import { errorMiddleware, resolveServerBaseUrl } from './client';

/**
 * Per-request API client for SSR loaders / actions. Forwards the inbound
 * `Cookie` header so the backend's session cookie reaches the API on
 * server-side fetches. `credentials: 'include'` is browser-only and has no
 * effect on Node — explicit cookie forwarding is what makes this work.
 *
 * Must never be imported by browser-side code; use `apiClient` instead.
 */
export function serverApiClient(request: Request) {
  const cookie = request.headers.get('cookie') ?? '';
  const client = createClient<paths>({
    baseUrl: resolveServerBaseUrl(),
    headers: cookie ? { cookie } : {},
  });
  client.use(errorMiddleware);
  return client;
}
