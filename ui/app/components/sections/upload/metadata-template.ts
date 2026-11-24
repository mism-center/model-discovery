import type { AnnotationTemplate } from './metadata-types';

/**
 * Source-of-truth field annotation template for metadata.yaml.
 *
 * Keys are dotted paths into the parsed YAML structure.
 * Fields absent from this template are not rendered.
 *
 * Visibility:
 *   'editable' → renders as a pre-populated text input or textarea
 *   'viewable' → renders as a read-only label+value display
 */
export const ANNOTATION_TEMPLATE: AnnotationTemplate = {
  // Identity
  'model.name': {
    label: 'Model Name',
    visibility: 'editable',
    inputType: 'object-scalar',
    required: true,
    hidden: false,
    placeholder: 'Human-readable name of the model',
  },
  'model.short_description': {
    label: 'Short Description',
    visibility: 'editable',
    inputType: 'object-scalar',
    required: true,
    hidden: false,
    placeholder: 'One-sentence summary',
  },
  'model.long_description': {
    label: 'Long Description',
    visibility: 'editable',
    inputType: 'textarea',
    hidden: false,
    placeholder: 'Multi-sentence description of the model',
  },
  'model.version': {
    label: 'Version',
    visibility: 'viewable',
    inputType: 'object-scalar',
    required: true,
    hidden: false,
    placeholder: 'e.g. 1.0.0',
  },
  'model.external_identifier': {
    label: 'External Identifier',
    visibility: 'editable',
    inputType: 'text',
    required: true,
    hidden: false,
    description: 'Canonical URI, DOI, or BioModels ID',
    placeholder: 'e.g. BIOMD0000000001',
  },
  'model.license': {
    label: 'License',
    visibility: 'editable',
    inputType: 'text',
    required: true,
    hidden: false,
    description: 'SPDX identifier',
    placeholder: 'e.g. MIT, Apache-2.0, CC-BY-4.0',
  },

  // Model characteristics
  'model.multiscale': {
    label: 'Multiscale',
    visibility: 'viewable',
    inputType: 'boolean',
    required: true,
    hidden: false,
    description: 'Whether the model spans multiple biological scales',
  },
  'model.model_class': {
    label: 'Model Class',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
    description: 'Modeling approach (e.g. ODE, agent-based)',
  },
  'model.formalism': {
    label: 'Formalism',
    visibility: 'viewable',
    inputType: 'list-ontology',

    hidden: false,
    description: 'Mathematical formalism (e.g. deterministic ODE, stochastic)',
  },
  'model.determinism': {
    label: 'Determinism',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    forceReadOnly: false,
  },
  'model.time_dynamics': {
    label: 'Time Dynamics',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    forceReadOnly: false,
  },
  'model.spatial': {
    label: 'Spatial',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    forceReadOnly: false,
  },
  'model.model_scales': {
    label: 'Model Scales',
    visibility: 'viewable',
    inputType: 'list-scalar',
    required: true,
    hidden: false,
    description: 'Biological scales covered (e.g. molecular, cellular)',
  },

  // Biology
  'model.biology.species': {
    label: 'Species / Host Organism',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
  },
  'model.biology.infectious_agent': {
    label: 'Infectious Agent',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
  },
  'model.biology.health_condition': {
    label: 'Health Condition / Disease',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
  },
  'model.biology.biological_processes': {
    label: 'Biological Processes',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
  },
  'model.biology.molecular_entities': {
    label: 'Molecular Entities',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
  },
  'model.biology.proteins_genes': {
    label: 'Proteins / Genes',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },
  'model.biology.topic_category': {
    label: 'Topic Category',
    visibility: 'viewable',
    inputType: 'list-ontology',
    hidden: false,
  },

  // Resources
  'model.related_resources': {
    label: 'Related Resources',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },
  'model.funding': {
    label: 'Funding',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },

  // People
  'model.authors': {
    label: 'Authors',
    visibility: 'viewable',
    inputType: 'list-object',
    required: true,
    hidden: false,
    description: 'Intellectual creators of the model',
  },
  'model.contacts': {
    label: 'Contacts',
    visibility: 'viewable',
    inputType: 'list-object',
    required: true,
    hidden: false,
    description: 'Who to contact about this model',
  },
  'model.publications': {
    label: 'Publications',
    visibility: 'viewable',
    inputType: 'list-object',
    required: true,
    hidden: false,
  },

  // Provenance
  'provenance.annotated_at': {
    label: 'Annotated At',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
  },
  'provenance.annotated_by': {
    label: 'Annotated By',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
  },
  'provenance.human_review_required': {
    label: 'Human Review Required',
    visibility: 'viewable',
    inputType: 'boolean',
    hidden: false,
  },
  'provenance.notes': {
    label: 'Notes',
    visibility: 'viewable',
    inputType: 'static',
    hidden: false,
  },
  schema_version: {
    label: 'Schema Version',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
  },
  'provenance.source_root': {
    label: 'Source Root',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
  },
  'provenance.files_inspected': {
    label: 'Files Inspected',
    visibility: 'viewable',
    inputType: 'list-scalar',
    hidden: false,
  },
  'provenance.ontology_lookups': {
    label: 'Ontology Lookups',
    visibility: 'viewable',
    inputType: 'preformatted',
    hidden: false,
  },
  'provenance.unmapped_fields': {
    label: 'Unmapped Fields',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },
  'provenance.partial_annotation_scope': {
    label: 'Partial Annotation Scope',
    visibility: 'viewable',
    inputType: 'preformatted',
    hidden: false,
  },
};
