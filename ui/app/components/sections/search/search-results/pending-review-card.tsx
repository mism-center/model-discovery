import cn from 'classnames';
import { useNavigate } from 'react-router';
import { Button, useDisclosure } from '@heroui/react';
import { TrashIcon } from '@heroicons/react/24/outline';
import { WrenchIcon } from '@heroicons/react/24/solid';

import type { SearchResultItem } from '~/api';
import { ReviewCard } from '~/components/common/review-card';
import { DeletePendingReviewModal } from './delete-pending-review-modal';

interface PendingReviewCardProps {
  model: SearchResultItem;
}

export function PendingReviewCard({ model }: PendingReviewCardProps) {
  const navigate = useNavigate();
  const deleteModal = useDisclosure();

  return (
    <ReviewCard
      badge="Annotation Pending Review"
      model={model}
      titleAs="heading"
      showAuthors
      subtitle={
        model.description && (
          <p className="text-sm text-default-800 line-clamp-2 mt-2 leading-relaxed">
            {model.description}
          </p>
        )
      }
      actions={
        <>
          <DeletePendingReviewModal
            model={model}
            isOpen={deleteModal.isOpen}
            onClose={deleteModal.onClose}
          />
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
            startContent={<WrenchIcon className="size-4" />}
            onPress={() =>
              navigate(`/annotation-review?id=${encodeURIComponent(model.id)}`)
            }
          >
            Review
          </Button>
        </>
      }
    />
  );
}
