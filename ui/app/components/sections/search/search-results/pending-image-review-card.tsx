import cn from 'classnames';
import { useNavigate } from 'react-router';
import { Button, useDisclosure } from '@heroui/react';
import { TrashIcon } from '@heroicons/react/24/outline';
import { EyeIcon } from '@heroicons/react/24/solid';
import { CalendarIcon, UserIcon } from '@heroicons/react/16/solid';
import { useQueryClient } from '@tanstack/react-query';

import type { ModelListItem } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { AuthorListTooltip } from './author-list-tooltip';
import { DeletePendingReviewModal } from './delete-pending-review-modal';

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.valueOf())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

interface PendingImageReviewCardProps {
  model: ModelListItem;
  userId: string;
}

export function PendingImageReviewCard({
  model,
  userId,
}: PendingImageReviewCardProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const deleteModal = useDisclosure();
  const authors = model.authors ?? [];
  const displayDate = model.date_published ?? model.created_at;
  const container = model.containers?.[0];

  return (
    <div
      className={cn(
        'group relative p-6 rounded-2xl',
        'flex items-stretch justify-between gap-6',
        'transition-all duration-200',
        'bg-transparent hover:bg-warning/4',
        'hover:shadow-sm hover:shadow-warning/5 hover:-translate-y-px'
      )}
    >
      {/* Left content */}
      <div className="flex-1 min-w-0">
        {/* Badge */}
        <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center px-2 py-0.5',
                'rounded-xs bg-warning',
                'text-white text-[10px] font-bold uppercase tracking-wide'
              )}
            >
              Image Pending Review
            </span>
          </div>
        </div>

        {/* Title */}
        <h3
          className={cn(
            'relative w-fit text-xl font-bold font-headline text-primary',
            'after:absolute after:w-full after:h-0.5 after:-bottom-px after:left-0',
            'after:bg-primary after:content-[""]',
            'after:scale-x-0 after:origin-right after:transition-transform after:duration-150 after:ease-in-out',
            'group-hover:after:scale-x-100 group-hover:after:origin-left',
            'after:delay-0 group-hover:after:delay-150'
          )}
        >
          {model.name}
        </h3>

        {/* Container snippet — most actionable info for this workflow state.
            Falls back to description if no container is present. */}
        {container ? (
          <p className="text-sm text-default-900 mt-2">
            <span className="font-semibold capitalize">{container.kind}</span>
            {container.image_name && (
              <span className="font-mono"> · {container.image_name}</span>
            )}
            {container.registry && (
              <span className="text-default-800"> · {container.registry}</span>
            )}
            {container.file && (
              <span className="text-default-800"> ({container.file})</span>
            )}
          </p>
        ) : (
          model.description && (
            <p className="text-sm text-default-800 line-clamp-2 mt-2 leading-relaxed">
              {model.description}
            </p>
          )
        )}

        {/* Metadata row */}
        <div className="flex items-center gap-4 mt-3 min-h-8">
          <div
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2',
              'text-[11px] text-default-800 uppercase tracking-tight'
            )}
          >
            {authors.length > 0 ? (
              <AuthorListTooltip authors={authors} />
            ) : (
              model.owner && (
                <div className="flex items-center gap-1.5 font-medium text-primary">
                  <UserIcon className="size-3.5" />
                  <span>{model.owner}</span>
                </div>
              )
            )}
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="size-3.5" />
              <span>{formatDate(displayDate)}</span>
            </div>
          </div>
        </div>
      </div>

      <DeletePendingReviewModal
        model={model}
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.onClose}
        onDeleted={() =>
          queryClient.invalidateQueries({
            queryKey: modelKeys.pendingImageReview(userId),
          })
        }
      />

      {/* Right side actions */}
      <div className="flex flex-col justify-between items-end">
        <Button
          variant="flat"
          size="sm"
          isIconOnly
          className={cn(
            'bg-transparent rounded-lg hover:opacity-100! active:opacity-90!',
            'text-danger hover:bg-danger hover:text-white'
          )}
          onPress={deleteModal.onOpen}
        >
          <TrashIcon className="size-5" />
        </Button>
        <Button
          size="sm"
          color="warning"
          className="!h-8 min-w-32 px-5 rounded-lg text-sm font-bold text-white"
          startContent={<EyeIcon className="size-4" />}
          onPress={() => navigate(`/models/${encodeURIComponent(model.id)}`)}
        >
          Review
        </Button>
      </div>
    </div>
  );
}
