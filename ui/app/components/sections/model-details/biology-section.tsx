import type { ModelDetailResponse } from '~/api/endpoints/models';
import {
  ChipList,
  Field,
  SectionAbsence,
  SectionCard,
  hasItems,
} from './primitives';

/**
 * The biological subject matter. Pairs with model characterization — that
 * section is the mathematics, this one is what the mathematics is about — so the
 * two sit together rather than being split by the operational sections.
 *
 * `organisms` lives here rather than under provenance: the schema classifies it
 * as scientific metadata (schema.md `biology.species`), and it is the most
 * orienting biological fact, so it leads.
 */
export function BiologySection({ model }: { model: ModelDetailResponse }) {
  const hasContent = [
    model.organisms,
    model.infectious_agents,
    model.health_conditions,
    model.biological_processes,
    model.molecular_entities,
    model.proteins_genes,
  ].some((values) => hasItems(values));

  return (
    <SectionCard
      title="Biology"
      description="Organisms, entities and processes this model represents."
    >
      {hasContent ? (
        <dl className="grid gap-5 sm:grid-cols-2">
          <Field label="Organisms">
            <ChipList values={model.organisms} tone="neutral" />
          </Field>
          <Field label="Infectious agents">
            <ChipList values={model.infectious_agents} tone="neutral" />
          </Field>
          <Field label="Health conditions">
            <ChipList values={model.health_conditions} tone="neutral" />
          </Field>
          <Field label="Biological processes">
            <ChipList values={model.biological_processes} tone="neutral" />
          </Field>
          <Field label="Molecular entities">
            <ChipList values={model.molecular_entities} tone="neutral" />
          </Field>
          <Field label="Proteins / genes">
            <ChipList values={model.proteins_genes} tone="neutral" />
          </Field>
        </dl>
      ) : (
        <SectionAbsence>
          No biological entities or processes have been recorded for this model.
        </SectionAbsence>
      )}
    </SectionCard>
  );
}
