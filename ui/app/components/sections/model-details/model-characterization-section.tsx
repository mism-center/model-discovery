import type { ModelDetailResponse } from '~/api/endpoints/models';
import {
  ChipList,
  Field,
  SectionAbsence,
  SectionCard,
  hasItems,
  hasValue,
  sentenceCase,
} from './primitives';

/** Render a nullable boolean as Yes / No, or '' so the field states the absence. */
function formatTristate(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return '';
  return value ? 'Yes' : 'No';
}

/** Vocabulary value, or '' so the field states the absence. */
function formatVocabulary(value: string | null | undefined): string {
  return hasValue(value) ? sentenceCase(value.trim()) : '';
}

/**
 * How the model is classified mathematically and dynamically (schema.md
 * Section A) — the orienting information for everything below it, which is why
 * it leads the page.
 */
export function ModelCharacterizationSection({
  model,
}: {
  model: ModelDetailResponse;
}) {
  const hasContent =
    hasItems(model.model_class) ||
    hasItems(model.formalism) ||
    hasValue(model.determinism) ||
    hasValue(model.time_dynamics) ||
    hasValue(model.spatial) ||
    typeof model.multiscale === 'boolean';

  return (
    <SectionCard
      title="Model characterization"
      description="How this model is classified mathematically and dynamically."
    >
      {hasContent ? (
        <dl className="grid gap-5 sm:grid-cols-2">
          <Field label="Model class">
            <ChipList values={model.model_class} facet="model_class" />
          </Field>
          <Field label="Formalism">
            <ChipList values={model.formalism} facet="formalism" />
          </Field>
          <Field label="Determinism">
            {formatVocabulary(model.determinism)}
          </Field>
          <Field label="Time dynamics">
            {formatVocabulary(model.time_dynamics)}
          </Field>
          <Field label="Spatial">{formatVocabulary(model.spatial)}</Field>
          <Field label="Multiscale">{formatTristate(model.multiscale)}</Field>
        </dl>
      ) : (
        <SectionAbsence>
          This model has not been characterized, so its class, formalism and
          dynamics are unknown.
        </SectionAbsence>
      )}
    </SectionCard>
  );
}
