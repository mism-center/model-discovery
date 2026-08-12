import { useState } from 'react';
import cn from 'classnames';
import { Button } from '@heroui/react';
import {
  CloudIcon,
  ExclamationCircleIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  WifiIcon,
} from '@heroicons/react/24/outline';
import { ArrowPathIcon } from '@heroicons/react/16/solid';

import { ApiError } from '~/api';

interface ApiErrorDisplayProps {
  error: unknown;
  title?: string;
  /** Called when the user clicks the retry button. Omit to hide the button. */
  onRetry?: () => void;
  className?: string;
}

/**
 * Quiet inline error state for failed API calls.
 *
 */
export function ApiErrorDisplay({
  error,
  title = 'Something went wrong',
  onRetry,
  className,
}: ApiErrorDisplayProps) {
  const apiError = error instanceof ApiError ? error : undefined;
  const isDev = import.meta.env.DEV;

  const { description, Icon } = summarize(apiError);

  return (
    <div className={cn('flex flex-col gap-6', className)} role="alert">
      <div className="flex flex-col items-center text-center gap-3 py-10">
        <Icon
          className="size-10 text-default-700"
          aria-hidden="true"
          strokeWidth={1.25}
        />
        <div className="flex flex-col gap-1 max-w-sm">
          <h3 className="text-base font-semibold text-default-900">{title}</h3>
          <p className="text-sm text-default-800 leading-relaxed">
            {description}
          </p>
        </div>
        {onRetry && (
          <Button
            size="sm"
            color="primary"
            variant="light"
            onPress={onRetry}
            startContent={<ArrowPathIcon className="size-3.5" />}
            className="mt-2 font-semibold"
          >
            Try again
          </Button>
        )}
      </div>

      {isDev && <DevDetails error={error} />}
    </div>
  );
}

function summarize(apiError: ApiError | undefined) {
  if (apiError?.isNetworkError) {
    return {
      description:
        "We couldn't reach the server. Check your connection and try again.",
      Icon: WifiIcon,
    };
  }

  if (apiError && apiError.status >= 500) {
    return {
      description:
        'The service is temporarily unavailable. Please try again in a moment.',
      Icon: CloudIcon,
    };
  }

  if (apiError?.isAuthError) {
    return {
      description: 'You may need to sign in to see this content.',
      Icon: LockClosedIcon,
    };
  }

  // 404 is the most likely failure on any id-keyed route, and it was falling
  // through to the generic "unexpected error" copy.
  if (apiError?.status === 404) {
    return {
      description: "This item doesn't exist, or you don't have access to it.",
      Icon: MagnifyingGlassIcon,
    };
  }

  return {
    description: 'An unexpected error occurred while loading this content.',
    Icon: ExclamationCircleIcon,
  };
}

function DevDetails({ error }: { error: unknown }) {
  const [open, setOpen] = useState(false);
  const apiError = error instanceof ApiError ? error : undefined;
  const stack = error instanceof Error ? error.stack : undefined;

  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      className="border border-default-200 rounded-md bg-default-50 text-xs"
    >
      <summary className="cursor-pointer select-none px-3 py-2 font-mono font-semibold text-default-800 uppercase tracking-wider text-[10px]">
        Error details
      </summary>
      <div className="flex flex-col gap-3 p-3 pt-0 font-mono text-[11px] text-default-900">
        {apiError && (
          <Field label="type">
            <span>
              {apiError.name} &bull; {apiError.code} &bull; HTTP{' '}
              {apiError.status === 0 ? 'N/A' : apiError.status}
            </span>
          </Field>
        )}
        {apiError?.url && (
          <Field label="url">
            <span className="break-all">{apiError.url}</span>
          </Field>
        )}
        {error instanceof Error && (
          <Field label="message">
            <span className="break-words">{error.message}</span>
          </Field>
        )}
        {apiError?.body !== undefined && apiError.body !== null && (
          <Field label="body">
            <pre className="whitespace-pre-wrap break-words rounded bg-default-100 p-2 max-h-64 overflow-auto">
              {formatBody(apiError.body)}
            </pre>
          </Field>
        )}
        {stack && (
          <Field label="stack">
            <pre className="whitespace-pre-wrap break-words rounded bg-default-100 p-2 max-h-64 overflow-auto">
              {stack}
            </pre>
          </Field>
        )}
      </div>
    </details>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[9px] uppercase tracking-widest text-default-800">
        {label}
      </span>
      <div>{children}</div>
    </div>
  );
}

function formatBody(body: unknown): string {
  if (typeof body === 'string') return body;
  try {
    return JSON.stringify(body, null, 2);
  } catch {
    return String(body);
  }
}
