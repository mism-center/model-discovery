import type { components } from '~/api/generated/schema';
import { API_BASE_URL, apiClient } from '~/api/client/client';

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
 */
export function resourceDownloadUrl(resourceId: string, file?: string): string {
  const url = new URL(
    `/api/v1/resources/${encodeURIComponent(resourceId)}/download`,
    API_BASE_URL
  );
  if (file) url.searchParams.set('file', file);
  return url.toString();
}
