import { ArrowRightIcon } from '@heroicons/react/16/solid';
import { useMutation } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router';

import type { CairnsEvidenceCard } from '~/api/endpoints/cairns';
import { loginHref, useUser } from '~/api/auth/user';
import { importBioModelsModel } from '~/api/endpoints/imports';

/**
 * Card actions read as links, matching the in-context action treatment used in
 * `run-output-files.tsx` and `terms-checkbox-group.tsx`. `text-xs` because the
 * column these sit in is 246px wide and its other content is `text-xs`.
 *
 * Importing is a mutation, so it stays a real `<button>` — only the appearance
 * is borrowed.
 */
const ACTION_LINK_BASE =
  'inline-flex items-center gap-1 text-xs font-semibold hover:underline ' +
  'outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded';

export const ACTION_LINK = `${ACTION_LINK_BASE} text-primary`;

/** Signing in is the lesser action here, so it stays visually secondary. */
const MUTED_ACTION_LINK = `${ACTION_LINK_BASE} text-default-800`;

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
      <Link className={ACTION_LINK} to={`/models/${card.mism_model_id}`}>
        View in registry
        <ArrowRightIcon className="size-3.5" />
      </Link>
    );
  }

  // No accession means the BioModels lookup failed, and the import re-fetches
  // the same record — so there is nothing to offer yet.
  if (card.source !== 'biomodels' || !accession) return;

  if (!user) {
    return (
      <a
        className={MUTED_ACTION_LINK}
        href={loginHref(location.pathname, location.search)}
      >
        Sign in to import
      </a>
    );
  }

  return (
    <>
      <button
        className={`${ACTION_LINK} disabled:opacity-60 disabled:no-underline`}
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
        type="button"
      >
        {mutation.isPending ? 'Importing…' : 'Import'}
      </button>
      {mutation.isError ? (
        <p className="basis-full text-[11px] leading-4 text-danger">
          {mutation.error.message}
        </p>
      ) : undefined}
    </>
  );
}
