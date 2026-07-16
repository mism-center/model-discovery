import type {
  ParsedMetadataYaml,
  FormValues,
  SchemaLeaf,
  OntologyLeaf,
} from './metadata-types';

// ── Extract FormValues from parsed YAML objects ───────────────────────────────
// Only the `value` property of {value, source, confidence} envelopes is stored
// in form state. The original parsed object is kept separately and used when
// reconstructing YAML, so source and confidence are always preserved.

export function extractFormValues(parsedMeta: ParsedMetadataYaml): FormValues {
  const values: FormValues = {};
  const model = parsedMeta.model ?? {};
  const metaProv = parsedMeta.provenance ?? {};

  values['schema_version'] = String(parsedMeta.schema_version ?? '');

  // ── metadata.yaml scalar fields ──
  values['model.name'] = leafString(model.name);
  values['model.name.$confidence'] = leafConfidence(model.name);
  values['model.short_description'] = leafString(model.short_description);
  values['model.short_description.$confidence'] = leafConfidence(
    model.short_description
  );
  values['model.long_description'] = leafString(model.long_description);
  values['model.long_description.$confidence'] = leafConfidence(
    model.long_description
  );
  values['model.version'] = leafString(model.version);
  values['model.version.$confidence'] = leafConfidence(model.version);
  values['model.external_identifier'] =
    model.external_identifier == null
      ? ''
      : String(model.external_identifier.value ?? '');
  values['model.license'] = String(
    model.license?.spdx_id ?? model.license?.name ?? ''
  );
  values['model.license.$confidence'] = String(model.license?.confidence ?? '');
  values['model.multiscale'] = leafString(
    model.multiscale as SchemaLeaf | undefined
  );
  values['model.determinism'] = String(model.determinism ?? '');
  values['model.time_dynamics'] = String(model.time_dynamics ?? '');
  values['model.spatial'] = String(model.spatial ?? '');

  // List fields: comma-joined label strings for display
  values['model.model_class'] = ontologyListString(model.model_class);
  values['model.formalism'] = ontologyListString(model.formalism);
  values['model.model_scales'] = scalarListString(model.model_scales);
  values['model.biology.species'] = ontologyListString(model.biology?.species);
  values['model.biology.infectious_agent'] = ontologyListString(
    model.biology?.infectious_agent
  );
  values['model.biology.health_condition'] = ontologyListString(
    model.biology?.health_condition
  );
  values['model.biology.biological_processes'] = ontologyListString(
    model.biology?.biological_processes
  );
  values['model.biology.molecular_entities'] = ontologyListString(
    model.biology?.molecular_entities
  );
  values['model.biology.proteins_genes'] = scalarListString(
    model.biology?.proteins_genes
  );
  values['model.biology.topic_category'] = ontologyListString(
    model.biology?.topic_category
  );

  // Per-item editable sub-fields for list-ontology arrays
  const ontologyFields: [string, OntologyLeaf[] | undefined][] = [
    ['model.model_class', model.model_class],
    ['model.formalism', model.formalism],
    ['model.biology.species', model.biology?.species],
    ['model.biology.infectious_agent', model.biology?.infectious_agent],
    ['model.biology.health_condition', model.biology?.health_condition],
    ['model.biology.biological_processes', model.biology?.biological_processes],
    ['model.biology.molecular_entities', model.biology?.molecular_entities],
    ['model.biology.topic_category', model.biology?.topic_category],
  ];
  for (const [fieldKey, list] of ontologyFields) {
    if (!Array.isArray(list)) continue;
    for (const [i, item] of list.entries()) {
      values[`${fieldKey}[${i}].confidence`] =
        item.confidence == null ? '' : String(item.confidence);
      values[`${fieldKey}[${i}].mapping_confidence`] =
        item.mapping_confidence ?? '';
      values[`${fieldKey}[${i}].value`] =
        item.value == null ? '' : String(item.value);
      values[`${fieldKey}[${i}].iri`] =
        item.iri == null ? '' : String(item.iri);
      values[`${fieldKey}[${i}].ontology_label`] =
        item.ontology_label != null
          ? String(item.ontology_label)
          : item.value != null
          ? String(item.value)
          : '';
      values[`${fieldKey}[${i}].ontology`] =
        item.ontology == null ? '' : String(item.ontology);
      values[`${fieldKey}[${i}].source`] =
        item.source == null ? '' : String(item.source);
    }
  }

  // Provenance display values
  values['provenance.annotated_at'] = String(metaProv['annotated_at'] ?? '');
  values['provenance.annotated_by'] = String(metaProv['annotated_by'] ?? '');
  values['provenance.human_review_required'] = String(
    metaProv['human_review_required'] ?? ''
  );
  values['provenance.notes'] = String(metaProv['notes'] ?? '');
  values['provenance.source_root'] = String(metaProv['source_root'] ?? '');
  values['provenance.files_inspected'] = scalarListString(
    metaProv['files_inspected'] as unknown[] | undefined
  );
  values['provenance.ontology_lookups'] =
    metaProv['ontology_lookups'] == null
      ? ''
      : JSON.stringify(metaProv['ontology_lookups'], null, 2);
  values['provenance.partial_annotation_scope'] =
    metaProv['partial_annotation_scope'] == null
      ? ''
      : JSON.stringify(metaProv['partial_annotation_scope'], null, 2);

  return values;
}

// ── Apply FormValues back into parsed YAML objects ────────────────────────────
// Only the fields declared as `editable` in the template are touched.
// All other fields pass through unchanged, preserving source/confidence/iri.

export function applyFormValuesToMetadata(
  original: ParsedMetadataYaml,
  values: FormValues
): ParsedMetadataYaml {
  const model = { ...original.model };

  model.name = applyLeaf(
    model.name,
    values['model.name'],
    values['model.name.$confidence']
  );
  model.short_description = applyLeaf(
    model.short_description,
    values['model.short_description'],
    values['model.short_description.$confidence']
  );
  model.long_description = applyLeaf(
    model.long_description,
    values['model.long_description'],
    values['model.long_description.$confidence']
  );
  model.version = applyLeaf(
    model.version,
    values['model.version'],
    values['model.version.$confidence']
  );

  const extIdValue = values['model.external_identifier'];
  if (model.external_identifier !== undefined) {
    model.external_identifier = {
      ...model.external_identifier,
      value: extIdValue,
    };
  } else if (extIdValue) {
    model.external_identifier = { value: extIdValue };
  }

  const licenseValue = values['model.license'];
  const licenseConfidence = values['model.license.$confidence'];
  const licenseConfidenceField = licenseConfidence
    ? { confidence: licenseConfidence }
    : {};
  if (model.license !== undefined) {
    model.license = {
      ...model.license,
      spdx_id: licenseValue,
      ...licenseConfidenceField,
    };
  } else if (licenseValue) {
    model.license = { spdx_id: licenseValue, ...licenseConfidenceField };
  }

  // Scalar viewable fields — always written back so edits made via section
  // edit mode are preserved on Approve.
  const multiscaleStr = values['model.multiscale'];
  const multiscaleLookup: Record<string, boolean> = {
    true: true,
    false: false,
  };
  model.multiscale =
    multiscaleStr in multiscaleLookup ? multiscaleLookup[multiscaleStr] : null;
  model.determinism = values['model.determinism'] || null;
  model.time_dynamics = values['model.time_dynamics'] || null;
  model.spatial = values['model.spatial'] || null;

  // Per-item confidence write-back for list-ontology arrays
  model.model_class = applyOntologyListItems(
    model.model_class,
    'model.model_class',
    values
  );
  model.formalism = applyOntologyListItems(
    model.formalism,
    'model.formalism',
    values
  );
  const biology = { ...model.biology };
  biology.species = applyOntologyListItems(
    biology.species,
    'model.biology.species',
    values
  );
  biology.infectious_agent = applyOntologyListItems(
    biology.infectious_agent,
    'model.biology.infectious_agent',
    values
  );
  biology.health_condition = applyOntologyListItems(
    biology.health_condition,
    'model.biology.health_condition',
    values
  );
  biology.biological_processes = applyOntologyListItems(
    biology.biological_processes,
    'model.biology.biological_processes',
    values
  );
  biology.molecular_entities = applyOntologyListItems(
    biology.molecular_entities,
    'model.biology.molecular_entities',
    values
  );
  biology.topic_category = applyOntologyListItems(
    biology.topic_category,
    'model.biology.topic_category',
    values
  );
  model.biology = biology;

  // Provenance write-back
  const provenance: Record<string, unknown> = {
    ...original.provenance,
    ['annotated_at']: values['provenance.annotated_at'] || null,
    ['annotated_by']: values['provenance.annotated_by'] || null,
  };
  const hrvStr = values['provenance.human_review_required'];
  const hrvLookup: Record<string, boolean> = { true: true, false: false };
  provenance['human_review_required'] =
    hrvStr in hrvLookup ? hrvLookup[hrvStr] : null;

  return { ...original, model, provenance };
}

function applyOntologyListItems(
  list: OntologyLeaf[] | undefined,
  fieldKey: string,
  values: FormValues
): OntologyLeaf[] | undefined {
  if (!Array.isArray(list)) return list;
  return list.map((item, i) => {
    const confidence = values[`${fieldKey}[${i}].confidence`];
    const mappingConfidence = values[`${fieldKey}[${i}].mapping_confidence`];
    const value = values[`${fieldKey}[${i}].value`];
    const iri = values[`${fieldKey}[${i}].iri`];
    const ontologyLabel = values[`${fieldKey}[${i}].ontology_label`];
    const ontology = values[`${fieldKey}[${i}].ontology`];
    const source = values[`${fieldKey}[${i}].source`];
    return {
      ...item,
      ...(confidence === undefined ? {} : { confidence: confidence || null }),
      ...(mappingConfidence === undefined
        ? {}
        : { mapping_confidence: mappingConfidence || null }),
      ...(value === undefined ? {} : { value: value || null }),
      ...(iri === undefined ? {} : { iri: iri || null }),
      ...(ontologyLabel === undefined ? {} : { ontology_label: ontologyLabel || null }),
      ...(ontology === undefined ? {} : { ontology: ontology || null }),
      ...(source === undefined ? {} : { source: source || undefined }),
    };
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function leafString(field: SchemaLeaf | boolean | undefined | null): string {
  if (field === null || field === undefined) return '';
  if (typeof field === 'boolean') return String(field);
  if (typeof field === 'object' && 'value' in field) {
    return field.value === null || field.value === undefined
      ? ''
      : String(field.value);
  }
  return '';
}

function applyLeaf(
  existing: SchemaLeaf | undefined,
  newValue: string | undefined,
  newConfidence: string | undefined
): SchemaLeaf {
  const base = { ...existing, value: newValue ?? null };
  if (newConfidence !== undefined && newConfidence !== '') {
    base.confidence = newConfidence;
  }
  return base as SchemaLeaf;
}

function leafConfidence(
  field: SchemaLeaf | boolean | undefined | null
): string {
  if (field === null || field === undefined || typeof field !== 'object')
    return '';
  return field.confidence !== null && field.confidence !== undefined
    ? String(field.confidence)
    : '';
}

function ontologyListString(list: OntologyLeaf[] | undefined): string {
  if (!Array.isArray(list)) return '';
  return list
    .map((item) => {
      const label = item.ontology_label ?? item.value;
      return label ? String(label) : '';
    })
    .filter(Boolean)
    .join(', ');
}

function scalarListString(list: unknown[] | undefined): string {
  if (!Array.isArray(list)) return '';
  return list
    .map((item) => {
      if (typeof item === 'string') return item;
      if (typeof item === 'object' && item !== null) {
        const record = item as Record<string, unknown>;
        const v = record['value'];
        return v == null ? '' : String(v);
      }
      return '';
    })
    .filter(Boolean)
    .join(', ');
}
