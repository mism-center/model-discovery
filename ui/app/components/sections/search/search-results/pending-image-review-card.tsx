import { useNavigate } from 'react-router';
import { Button } from '@heroui/react';
import { EyeIcon } from '@heroicons/react/24/solid';

import type { ModelListItem } from '~/api/endpoints/models';
import { ReviewCard } from '~/components/common/review-card';

interface PendingImageReviewCardProps {
  model: ModelListItem;
}

export function PendingImageReviewCard({ model }: PendingImageReviewCardProps) {
  const navigate = useNavigate();
  const container = model.containers?.[0];

  return (
    <ReviewCard
      badge="Image Pending Review"
      model={model}
      titleAs="heading"
      showAuthors
      subtitle={
        container ? (
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
        )
      }
      actions={
        <>
          {/*
           * No delete action here. Models at this stage are APPROVED and
           * publicly visible — deletion is a destructive action on a live
           * record that may already be referenced by other users. The rules
           * around what an owner may do to a fully-public model (delete,
           * withdraw, retract) have not been decided yet. Revisit once
           * that policy is defined.
           *
           * If a "cancel image submission" affordance is ever added it
           * should reset image_review_status to NOT_APPLICABLE via a
           * dedicated endpoint, not delete the model entirely.
           */}
          <Button
            size="sm"
            color="warning"
            className="!h-8 min-w-32 px-5 rounded-lg text-sm font-bold text-white"
            startContent={<EyeIcon className="size-4" />}
            onPress={() => navigate(`/models/${encodeURIComponent(model.id)}`)}
          >
            View model
          </Button>
        </>
      }
    />
  );
}
