import { ArrowDownTrayIcon, ArrowRightIcon } from '@heroicons/react/16/solid';
import { Button } from '@heroui/react';
import { useMutation } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';
import { loginHref, useUser } from '~/api/auth/user';
import { importBioModelsModel } from '~/api/endpoints/imports';

/**
 * Bring a BioModels record into this registry, or link to it if it is already
 * here.
 *
 * `mism_model_id` is populated server-side under the same visibility rule as
 * the model pages: an approved import resolves for everyone, an unapproved one
 * only for whoever started it. So a signed-out visitor is offered sign-in
 * rather than an import that would 401, and a link only ever points somewhere
 * the caller can actually open.
 */
export function EvidenceImportAction({ card }: { card: CairnsEvidenceCard }) {
  const { user } = useUser();
  const location = useLocation();
  const navigate = useNavigate();

  const accession = card.biomodels?.identifier;

  const mutation = useMutation({
    mutationFn: () => importBioModelsModel(accession ?? ''),
    onSuccess: (result) => navigate(`/annotation-review?id=${result.model_id}`),
  });

  if (card.mism_model_id) {
    return (
      <Button
        as={Link}
        className="text-primary"
        endContent={<ArrowRightIcon className="size-3.5" />}
        size="sm"
        to={`/models/${card.mism_model_id}`}
        variant="flat"
      >
        View in registry
      </Button>
    );
  }

  // No accession means the BioModels lookup failed, and the import re-fetches
  // the same record — so there is nothing to offer yet.
  if (card.source !== 'biomodels' || !accession) return;

  if (!user) {
    return (
      <Button
        as="a"
        className="text-default-800"
        href={loginHref(location.pathname, location.search)}
        size="sm"
        variant="flat"
      >
        Sign in to import
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Button
        className="text-primary"
        isLoading={mutation.isPending}
        onPress={() => mutation.mutate()}
        size="sm"
        startContent={
          mutation.isPending ? undefined : (
            <ArrowDownTrayIcon className="size-3.5" />
          )
        }
        variant="flat"
      >
        {mutation.isPending ? 'Importing…' : 'Import'}
      </Button>
      {mutation.isError ? (
        <p className="text-[11px] leading-4 text-danger">
          {mutation.error.message}
        </p>
      ) : undefined}
    </div>
  );
}
