import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';
import { browserApiBaseUrl } from '~/utils/env';

export type ResourceFileItem = components['schemas']['ResourceFileItem'];
export type ResourceFilesResponse =
  components['schemas']['ResourceFilesResponse'];

export async function listResourceFiles(
  resourceId: string,
  options: { signal?: AbortSignal; client?: Client<paths> } = {}
): Promise<ResourceFilesResponse> {
  const { data } = await (options.client ?? apiClient).GET(
    '/api/v1/resources/{resource_id}/files',
    {
      params: { path: { resource_id: resourceId } },
      signal: options.signal,
    }
  );
  return data as ResourceFilesResponse;
}

/**
 * Build an absolute URL for the resource download endpoint.
 *
 * Used as an `href` on plain anchor tags so the browser handles the download
 * natively (no in-memory blob, native progress UI). Omit `file` to download
 * the whole resource directory as a zip.
 */
export function resourceDownloadUrl(resourceId: string, file?: string): string {
  // browserApiBaseUrl() is '' for same-origin (shared ingress); fall back to
  // the current origin so `new URL()` has an absolute base to resolve against.
  const base = browserApiBaseUrl() || globalThis.location?.origin;
  const url = new URL(
    `/api/v1/resources/${encodeURIComponent(resourceId)}/download`,
    base
  );
  if (file) url.searchParams.set('file', file);
  return url.toString();
}
