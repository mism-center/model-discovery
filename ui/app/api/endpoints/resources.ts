import type { components } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';
import { browserApiBaseUrl } from '~/utils/env';

export type ResourceFileItem = components['schemas']['ResourceFileItem'];
export type ResourceFilesResponse =
  components['schemas']['ResourceFilesResponse'];

export async function listResourceFiles(
  resourceId: string,
  options: { signal?: AbortSignal } = {}
): Promise<ResourceFilesResponse> {
  const { data } = await apiClient.GET(
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
 *
 * Pass `{ inline: true }` (single file only) to request the preview variant:
 * the backend serves it with a content type guessed from the extension and an
 * `inline` disposition, so the browser renders it (e.g. as an `<img src>`)
 * instead of forcing a download.
 */
export function resourceDownloadUrl(
  resourceId: string,
  file?: string,
  options: { inline?: boolean } = {}
): string {
  // browserApiBaseUrl() is '' for same-origin (shared ingress); fall back to
  // the current origin so `new URL()` has an absolute base to resolve against.
  const base = browserApiBaseUrl() || globalThis.location?.origin;
  const url = new URL(
    `/api/v1/resources/${encodeURIComponent(resourceId)}/download`,
    base
  );
  if (file) url.searchParams.set('file', file);
  // `inline` only applies to a single file; the zip is always an attachment.
  if (file && options.inline) url.searchParams.set('disposition', 'inline');
  return url.toString();
}

/**
 * Largest text file we will fetch for an in-app preview. Bigger files show a
 * "download instead" message rather than being pulled into memory.
 */
export const TEXT_PREVIEW_MAX_BYTES = 1_500_000;

/**
 * Fetch the raw text content of a single file for previewing. Uses the inline
 * download URL (real content type) but reads the body as text. Cookies are
 * sent for same-origin/credentialed auth, matching the API client.
 */
export async function fetchResourceFileText(
  resourceId: string,
  file: string,
  options: { signal?: AbortSignal } = {}
): Promise<string> {
  const url = resourceDownloadUrl(resourceId, file, { inline: true });
  const res = await fetch(url, {
    credentials: 'include',
    signal: options.signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to load file (${res.status.toString()})`);
  }
  return res.text();
}
