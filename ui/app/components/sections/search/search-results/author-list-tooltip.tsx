import { Divider, Tooltip } from '@heroui/react';
import { UserIcon } from '@heroicons/react/16/solid';
import pluralize from 'pluralize';

import type { Author } from '~/api';

export function AuthorListTooltip({ authors }: { authors: Author[] }) {
  if (authors.length === 0) return null;

  return (
    <Tooltip
      delay={125}
      closeDelay={125}
      showArrow
      placement="bottom-start"
      color="foreground"
      isDisabled={authors.length < 2}
      classNames={{
        base: 'before:bg-slate-800 before:z-11 before:shadow-none before:rounded-none',
        content: 'p-5 bg-slate-800 border border-white/10 rounded-sm',
      }}
      // Result card is an anchor, need to prevent unintuitive redirect behavior from clicks on this tooltip
      onClick={(e) => e.preventDefault()}
      content={
        <div className="flex flex-col text-white">
          <span className="text-[12px] font-bold uppercase tracking-widest text-[#adcdcd]">
            Contributors
          </span>
          <Divider className="mt-2 mb-3 bg-white/10" />
          <div className="flex flex-col gap-3">
            {authors.map((author) => (
              <div
                key={`${author.name}-${author.orcid}`}
                className="flex flex-col"
              >
                <span className="text-sm font-bold">{author.name}</span>
                {author.affiliation && (
                  <span className="text-[11px] text-slate-300">
                    {author.affiliation}
                  </span>
                )}
                {author.role && (
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">
                    {author.role}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      }
    >
      <div className="flex items-center gap-1.5 font-medium text-primary">
        <UserIcon className="size-3.5" />
        <span>
          {authors[0].name}
          {authors.length > 1 && (
            <span> + {pluralize('other', authors.length - 1, true)}</span>
          )}
        </span>
      </div>
    </Tooltip>
  );
}
