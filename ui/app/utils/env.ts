const DEFAULT_TUSD_PLACEHOLDER_URL = 'http://localhost:8000';

/**
 * Browser API base URL: same-origin ('') so shared ingress routes `/api`.
 */
export function browserApiBaseUrl(): string {
  return '';
}

/**
 * Server API base URL: the in-cluster gateway origin, required for SSR fetches
 * where a relative URL has no host.
 */
export function serverApiBaseUrl(): string {
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

export function resolveTusdPlaceholderUrl(): string {
  if (globalThis.window !== undefined) {
    return (
      import.meta.env.VITE_TUSD_PLACEHOLDER_URL ?? DEFAULT_TUSD_PLACEHOLDER_URL
    );
  }

  return process.env.VITE_TUSD_PLACEHOLDER_URL ?? DEFAULT_TUSD_PLACEHOLDER_URL;
}
