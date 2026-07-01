const DEFAULT_TUSD_PLACEHOLDER_URL = 'http://localhost:8000';

export function resolveApiBaseUrl(): string {
  // Browser: default to same-origin '/api' so ingress can take care of routing.
  if (globalThis.window !== undefined) {
    return import.meta.env.VITE_API_BASE_URL ?? '';
  }

  // Server runtime: prefer pod env var.
  return process.env.VITE_API_BASE_URL ?? '';
}

export function resolveTusdPlaceholderUrl(): string {
  if (globalThis.window !== undefined) {
    return (
      import.meta.env.VITE_TUSD_PLACEHOLDER_URL ?? DEFAULT_TUSD_PLACEHOLDER_URL
    );
  }

  return process.env.VITE_TUSD_PLACEHOLDER_URL ?? DEFAULT_TUSD_PLACEHOLDER_URL;
}
