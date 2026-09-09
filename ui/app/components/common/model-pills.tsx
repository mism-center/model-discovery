import cn from 'classnames';

import type { components } from '~/api/generated/schema';

type RegistrationStatus =
  components['schemas']['ModelDetailResponse']['registration_status'];

/**
 * Badge scale. `card` is a search result row, `page` a detail-page header —
 * the same two scales `RunControls` distinguishes.
 */
export type PillScale = 'card' | 'page';

const BASE = 'inline-flex items-center px-2 py-0.5 rounded-xs uppercase';

function pillClass(scale: PillScale, tone: string): string {
  return cn(
    BASE,
    tone,
    scale === 'page'
      ? 'text-xs font-bold tracking-wide'
      : 'text-[10px] font-bold tracking-wide'
  );
}

/**
 * Whether a model can be launched.
 *
 * A null `execution_type` is the encoding for "not executable" rather than
 * missing data: a BioModels import ships no run recipe and nothing has built an
 * image for it, so it stays non-executable until a builder pass exists. Stated
 * in grey rather than left blank, because an absent badge reads as an oversight
 * next to models that carry one.
 */
export function ExecutionPill({
  executionType,
  scale = 'card',
}: {
  executionType: string | null | undefined;
  scale?: PillScale;
}) {
  if (executionType) {
    return (
      <span className={pillClass(scale, 'bg-primary text-white')}>
        Executable
      </span>
    );
  }
  return (
    <span className={pillClass(scale, 'bg-default-300 text-default-800')}>
      Non-executable
    </span>
  );
}

const STATUS_LABELS: Partial<Record<NonNullable<RegistrationStatus>, string>> =
  {
    draft: 'Draft',
    annotating: 'Annotating',
    annotation_failed: 'Annotation failed',
    pending_review: 'Pending review',
    rejected: 'Rejected',
  };

// `annotation_failed` and `rejected` are dead ends needing attention; the rest
// are ordinary stages of a model still working its way through registration.
const STALLED: ReadonlySet<string> = new Set(['annotation_failed', 'rejected']);

/**
 * Where a model sits in registration, shown only when that is not `approved`.
 *
 * Approved is the overwhelming majority and the state every other badge already
 * implies, so labelling it would cost a slot and answer nothing. Anything else
 * is a model the catalogue does not yet vouch for — which imports made common,
 * since they land `draft` and stay unapproved through annotation and review.
 */
export function RegistrationStatusPill({
  status,
  scale = 'card',
}: {
  status: RegistrationStatus;
  scale?: PillScale;
}) {
  const label = status ? STATUS_LABELS[status] : undefined;
  if (!status || !label) return;

  return (
    <span
      className={pillClass(
        scale,
        STALLED.has(status)
          ? 'bg-danger text-white'
          : 'bg-warning-600 text-white'
      )}
    >
      {label}
    </span>
  );
}
