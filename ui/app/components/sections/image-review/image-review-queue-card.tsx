import cn from 'classnames';
import { Button, useDisclosure } from '@heroui/react';
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { CalendarIcon, UserIcon } from '@heroicons/react/16/solid';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';

import { reviewModelContainerImage } from '~/api';
import type { ModelListItem } from '~/api/endpoints/models';
import { modelKeys } from '~/api/query/models';
import { ApiErrorDisplay } from '~/components/common/api-error-display';
import { RejectImageModal } from './reject-image-modal';

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

interface ImageReviewQueueCardProps {
  model: ModelListItem;
}

/**
 * A reviewer's approve/reject decision on one model's pending container
 * image (MISM-291, UI-Phase 6-B), via `POST /models/{id}/image-review`.
 *
 * Mirrors `ReviewQueueCard` (UI-Phase 4-B) exactly, one level down the
 * workflow: Approve fires directly (no modal — a routine, low-friction
 * action); Reject opens `RejectImageModal`, since the backend requires a
 * non-blank reason for it. Links to the model detail page, not an editor —
 * there is no owner-facing image editor to link to instead.
 */
export function ImageReviewQueueCard({ model }: ImageReviewQueueCardProps) {
  const queryClient = useQueryClient();
  const rejectModal = useDisclosure();
  const container = model.containers?.[0];
  const displayDate = model.date_published ?? model.created_at;

  const approveMutation = useMutation({
    mutationFn: () =>
      reviewModelContainerImage(model.id, { approve: true, reason: '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: modelKeys.imageReviewQueue(),
      });
    },
  });

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
      <div className="flex-1 min-w-0">
        <div className="flex items-center flex-wrap gap-x-3 gap-y-3 min-h-8 mb-1">
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

        <Link
          to={`/models/${encodeURIComponent(model.id)}`}
          className="text-xl font-bold font-headline text-primary hover:underline"
        >
          {model.name}
        </Link>

        {container && (
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
        )}

        <div className="flex items-center gap-4 mt-3 min-h-8">
          <div
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2',
              'text-[11px] text-default-800 uppercase tracking-tight'
            )}
          >
            {model.owner && (
              <div className="flex items-center gap-1.5 font-medium text-primary">
                <UserIcon className="size-3.5" />
                <span>{model.owner}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="size-3.5" />
              <span>{formatDate(displayDate)}</span>
            </div>
          </div>
        </div>

        {approveMutation.isError && (
          <ApiErrorDisplay
            error={approveMutation.error}
            title="Failed to approve"
            className="mt-3"
          />
        )}
      </div>

      <RejectImageModal
        model={model}
        isOpen={rejectModal.isOpen}
        onClose={rejectModal.onClose}
      />

      <div className="flex flex-col justify-between items-end gap-2">
        <Button
          size="sm"
          variant="flat"
          className={cn(
            'bg-transparent rounded-lg hover:opacity-100! active:opacity-90!',
            'text-danger hover:bg-danger hover:text-white'
          )}
          startContent={<XMarkIcon className="size-4" />}
          onPress={rejectModal.onOpen}
          isDisabled={approveMutation.isPending}
        >
          Reject
        </Button>
        <Button
          size="sm"
          color="primary"
          className="min-w-24 rounded-lg text-white font-bold"
          startContent={<CheckIcon className="size-4" />}
          onPress={() => approveMutation.mutate()}
          isLoading={approveMutation.isPending}
        >
          Approve
        </Button>
      </div>
    </div>
  );
}
