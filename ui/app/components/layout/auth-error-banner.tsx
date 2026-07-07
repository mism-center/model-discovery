import { Alert } from '@heroui/react';
import { useSearchParams } from 'react-router';

const AUTH_ERROR_PARAMS = ['auth_error', 'auth_error_description'] as const;

export function AuthErrorBanner() {
  const [searchParams, setSearchParams] = useSearchParams();
  const error = searchParams.get('auth_error');
  const description = searchParams.get('auth_error_description');

  if (!error) return null;

  const dismiss = () => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const key of AUTH_ERROR_PARAMS) next.delete(key);
        return next;
      },
      { replace: true, preventScrollReset: true }
    );
  };

  return (
    <div className="px-4 pt-3">
      <Alert
        color="danger"
        title="Sign-in failed"
        description={description || error}
        onClose={dismiss}
      />
    </div>
  );
}
