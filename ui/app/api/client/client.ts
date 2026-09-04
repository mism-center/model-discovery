import createClient, { type Middleware } from 'openapi-fetch';

import type { paths } from '~/api/generated/schema';
import { browserApiBaseUrl } from '~/utils/env';
import { ApiError } from './errors';

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
      code: extractErrorCode(body),
      status: response.status,
      body,
      url: request.url,
    });
  },
};

export const apiClient = createClient<paths>({
  baseUrl: browserApiBaseUrl(),
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

/**
 * Every error this app's own backends raise uses `{"error": {"code",
 * "detail"}}` (model-discovery's and execution-platform's shared
 * `APIError`/`PlatformError` exception-handler shape) — check that nested
 * shape first. `record.message`/`record.detail` remain as a fallback for
 * responses that don't go through either app's own handler, including
 * FastAPI's own request-validation errors (a top-level `detail`, either a
 * string or an array of `{msg, loc, type}` objects).
 */
function extractErrorMessage(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') return;
  const record = body as Record<string, unknown>;
  const nestedDetail = nestedErrorField(record, 'detail');
  if (typeof nestedDetail === 'string' && nestedDetail) return nestedDetail;
  if (typeof record.message === 'string') return record.message;
  if (typeof record.detail === 'string') return record.detail;
  if (Array.isArray(record.detail) && record.detail.length > 0) {
    const first = record.detail[0] as Record<string, unknown>;
    if (typeof first?.msg === 'string') return first.msg;
  }
  return;
}

/** Same nested `{"error": {"code", ...}}` shape as `extractErrorMessage`, for `ApiError.code`. */
function extractErrorCode(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') return;
  const code = nestedErrorField(body as Record<string, unknown>, 'code');
  return typeof code === 'string' && code ? code : undefined;
}

function nestedErrorField(
  record: Record<string, unknown>,
  field: string
): unknown {
  const nested = record.error;
  if (!nested || typeof nested !== 'object') return undefined;
  return (nested as Record<string, unknown>)[field];
}
