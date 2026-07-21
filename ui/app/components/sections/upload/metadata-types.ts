// ── Parsed YAML document shapes ──────────────────────────────────────────────
// These reflect what `yaml.parse()` returns from metadata.yaml.
// All nested `value` fields are nullable — the annotator may emit null when
// confidence is below threshold.

export type SchemaLeaf = {
  value: string | number | boolean | null;
  source?: string;
  confidence?: number | string | null;
};

export type OntologyLeaf = {
  value?: string | null;
  iri?: string | null;
  ontology_label?: string | null;
  ontology?: string | null;
  mapping_confidence?: string | null;
  source?: string;
  confidence?: number | string | null;
};

export type AuthorEntry = {
  name?: string | null;
  affiliation?: string | null;
  orcid?: string | null;
  role?: string | null;
  source?: string;
  confidence?: number | string | null;
};

export type ContactEntry = {
  name?: string | null;
  email?: string | null;
  affiliation?: string | null;
  role?: string | null;
  source?: string;
};

export type LicenseEntry = {
  spdx_id?: string | null;
  name?: string | null;
  source?: string;
  confidence?: number | string | null;
};

export type PublicationEntry = {
  title?: string | null;
  doi?: string | null;
  pmid?: string | null;
  url?: string | null;
  source?: string;
};

export type ExternalIdentifierEntry = {
  scheme?: string | null;
  value?: string | null;
  source?: string;
};

export type ParsedMetadataYaml = {
  schema_version?: string;
  model?: {
    name?: SchemaLeaf;
    short_description?: SchemaLeaf;
    long_description?: SchemaLeaf;
    version?: SchemaLeaf;
    external_identifier?: ExternalIdentifierEntry;
    model_class?: OntologyLeaf[];
    formalism?: OntologyLeaf[];
    determinism?: string | null;
    time_dynamics?: string | null;
    spatial?: string | null;
    multiscale?: SchemaLeaf | boolean | null;
    model_scales?: (SchemaLeaf | OntologyLeaf | string)[];
    biology?: {
      species?: OntologyLeaf[];
      infectious_agent?: OntologyLeaf[];
      health_condition?: OntologyLeaf[];
      topic_category?: OntologyLeaf[];
      biological_processes?: OntologyLeaf[];
      molecular_entities?: OntologyLeaf[];
      proteins_genes?: unknown[];
    };
    authors?: AuthorEntry[];
    contacts?: ContactEntry[];
    license?: LicenseEntry;
    publications?: PublicationEntry[];
    related_resources?: unknown[];
    funding?: unknown[];
  };
  provenance?: Record<string, unknown>;
};

// ── Template annotation types ─────────────────────────────────────────────────

export type FieldVisibility = 'editable' | 'viewable';

export type FieldInputType =
  | 'text' // single-line Input
  | 'textarea' // multi-line Textarea
  | 'boolean' // true/false chip display
  | 'list-scalar' // list of scalar leaves → comma-joined chips
  | 'list-object' // list of complex objects → mini cards
  | 'list-ontology' // list of OntologyLeaf → chips with label
  | 'list-entry-point' // list of EntryPointEntry → per-item editable cards (command, purpose, default_output_location)
  | 'list-container' // list of ContainerEntry → per-item editable cards (kind, file, image_name)
  | 'object-scalar' // single {value, source, confidence} envelope → text of `.value`
  | 'static' // read-only provenance / system field
  | 'preformatted'; // complex nested object → <pre> JSON block

export type FieldAnnotation = {
  /** Human-readable label shown in the form */
  label: string;
  /** Whether the field renders as an editable input or read-only display */
  visibility: FieldVisibility;
  /** How the value is rendered / edited */
  inputType: FieldInputType;
  /** Optional helper text shown below the field */
  description?: string;
  /** Optional placeholder for editable fields */
  placeholder?: string;
  /** Whether this is a REQUIRED field per schema — drives visual indicator */
  required?: boolean;
  /** When true, stays read-only even when the section Edit checkbox is on */
  forceReadOnly?: boolean;
  /** When true, the field is excluded from the form entirely */
  hidden?: boolean;
};

/** Template: keyed by dotted field path within metadata.yaml. */
export type AnnotationTemplate = Record<string, FieldAnnotation>;

/**
 * Flat map of fieldKey → current string value maintained in form state.
 * Keys are dotted paths: "model.name", "provenance.annotated_at", etc.
 */
export type FormValues = Record<string, string>;
