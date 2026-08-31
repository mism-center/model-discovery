import { Link as RouterLink } from 'react-router';
import { Button } from '@heroui/react';
import cn from 'classnames';
import { ArrowLeftIcon } from '@heroicons/react/16/solid';

/**
 * Shared shell for pages that are linked from global chrome (Header, Footer)
 * but not yet designed. Keeps those links from 404'ing and gives each page a
 * real route file to grow into — replace the placeholder body with content.
 */
export function PagePlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <main className="flex grow flex-col items-center justify-center bg-default-50 px-8 py-24">
      <div className="max-w-xl text-center">
        <p
          className={cn(
            'text-[11px] font-semibold uppercase tracking-[0.14em] text-secondary'
          )}
        >
          Coming soon
        </p>
        <h1 className="mt-3 font-headline text-3xl font-extrabold text-primary">
          {title}
        </h1>
        <p className="mt-4 text-base leading-relaxed text-default-800">
          {description}
        </p>
        <Button
          as={RouterLink}
          to="/search"
          color="primary"
          variant="flat"
          className="mt-8 font-medium"
          startContent={<ArrowLeftIcon className="size-4" />}
        >
          Back to search
        </Button>
      </div>
    </main>
  );
}
