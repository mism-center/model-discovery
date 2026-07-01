import createClient, { type Middleware } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import { resolveApiBaseUrl } from '~/utils/env';
import { ApiError } from './errors';

const BROWSER_BASE_URL = '';

export function resolveServerBaseUrl(): string {
  const url = process.env.API_BASE_URL;
  if (!url) {
    throw new Error(
      'API_BASE_URL is not set. Provide the in-cluster gateway origin for ' +
        'SSR fetches (e.g. http://localhost:8000 locally, ' +
        'http://discovery-gateway:8000 in cluster).'
    );
  }
  return url.replace(/\/$/, '');
}

/**
 * Normalize non-2xx responses into `ApiError` so call sites don't have to
 * branch on `{ data, error }` from openapi-fetch for error handling.
 * Successful responses pass through untouched.
 */
export const errorMiddleware: Middleware = {
  async onResponse({ response, request }) {
    if (response.ok) return;

    const contentType = response.headers.get('content-type') ?? '';
    const isJson = contentType.includes('application/json');
    const raw = await response.clone().text();
    const body: unknown = raw && isJson ? safeJsonParse(raw) : raw;

    throw new ApiError({
      message: extractErrorMessage(body) ?? `HTTP ${response.status}`,
      status: response.status,
      body,
      url: request.url,
    });
  },
};

export const apiClient = createClient<paths>({
  baseUrl: BROWSER_BASE_URL,
  // Browser sends cookies for same-origin (proxy / shared ingress) and
  // cross-origin (if CORS allow_credentials is configured).
  credentials: 'include',
});

apiClient.use(errorMiddleware);

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractErrorMessage(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') return;
  const record = body as Record<string, unknown>;
  if (typeof record.message === 'string') return record.message;
  if (typeof record.detail === 'string') return record.detail;
  if (Array.isArray(record.detail) && record.detail.length > 0) {
    const first = record.detail[0] as Record<string, unknown>;
    if (typeof first?.msg === 'string') return first.msg;
  }
  return;
}
