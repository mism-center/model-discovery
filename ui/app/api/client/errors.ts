/**
 * Normalized error class for all API failures.
 * (non-2xx responses, network errors, and validation)
 */
export class ApiError extends Error {
  /** HTTP status code, or 0 when no response was received (e.g. network error, abort). */
  readonly status: number;

  /** Short machine-readable code. Derived from status when the server doesn't supply one. */
  readonly code: string;

  /** Parsed response body, when available. */
  readonly body: unknown;

  /** The originating Request URL, if known. */
  readonly url?: string;

  constructor(options: {
    message: string;
    status: number;
    code?: string;
    body?: unknown;
    url?: string;
    cause?: unknown;
  }) {
    super(options.message, { cause: options.cause });
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code ?? codeForStatus(options.status);
    this.body = options.body;
    this.url = options.url;
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isValidationError(): boolean {
    return this.status === 422 || this.status === 400;
  }

  /** True when the request never left the client (network error, aborted, etc.). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

function codeForStatus(status: number): string {
  if (status === 0) return 'network_error';
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 422) return 'validation_error';
  if (status >= 500) return 'server_error';
  if (status >= 400) return 'client_error';
  return 'unknown';
}
