// ── Parsed YAML document shapes ──────────────────────────────────────────────
// These reflect what `yaml.parse()` returns from execution.yaml.
// Fields that may appear as a plain string OR a {value, source, confidence}
// envelope are typed as a union to handle both schema versions.

import type { OntologyLeaf, SchemaLeaf } from './metadata-types';

export type ArgumentEntry = {
  name?: string | null;
  description?: string | null;
  default?: unknown;
  enums?: unknown[] | null;
  data_type?: string | null;
  position?: number | null;
  user_can_override?: boolean | null;
};

export type EntryPointEntry = {
  /** Shell command used to invoke the model. REQUIRED per schema. */
  command?: string | null;
  /** Human-readable description of what this entry point does. REQUIRED per schema. */
  purpose?: string | null;
  /** Repo-relative path this entry writes results to. OPTIONAL. */
  default_output_location?: string | null;
  /** Legacy field from older schema revisions — kept for backward compat. */
  name?: string | null;
  arguments?: ArgumentEntry[];
  source?: string;
  confidence?: string | null;
};

export type DependencyEntry = {
  name?: string | null;
  version_constraint?: string | null;
  group?: string | null;
  source?: string;
};

export type ContainerEntry = {
  kind?: string | null;
  file?: string | null;
  image_name?: string | null;
  source?: string;
};

export type IoParameterEntry = {
  name?: string | null;
  description?: string | null;
  default_value?: unknown;
  /** Ontology-mapped to UO */
  unit?: OntologyLeaf | string | null;
  /** Ontology-mapped to GO/SBO */
  biological_meaning?: OntologyLeaf | null;
  source?: string;
  confidence?: string | null;
};

export type IoInitialConditionEntry = {
  name?: string | null;
  value?: unknown;
  unit?: OntologyLeaf | null;
  source?: string;
  confidence?: string | null;
};

export type IoDataInputEntry = {
  name?: string | null;
  purpose?: string | null;
  /** Ontology-mapped to EDAM:format */
  format?: OntologyLeaf | null;
  required?: boolean | null;
  source?: string;
  confidence?: string | null;
};

export type IoOutputEntry = {
  name?: string | null;
  description?: string | null;
  /** Ontology-mapped to GO/SBO/SIO */
  quantity_kind?: OntologyLeaf | null;
  /** Ontology-mapped to UO */
  unit?: OntologyLeaf | null;
  /** Ontology-mapped to EDAM:format */
  format?: OntologyLeaf | null;
  destination?: string | null;
  source?: string;
  confidence?: string | null;
};

export type ParsedExecutionYaml = {
  schema_version?: string;
  execution?: {
    /** Plain string ("characterized") or SchemaLeaf ({value, source, confidence}).
     *  Schema enumerates: "characterized" | "partially_characterized" | "not_determined". REQUIRED. */
    status?: string | SchemaLeaf | null;
    /** REQUIRED (sub-field `name` required). Ontology-mapped to SWO. */
    language?: {
      name?: string | null;
      version_constraint?: string | null;
      /** Older schema alias for version_constraint */
      version?: string | null;
      iri?: string | null;
      ontology?: string | null;
      source?: string;
    };
    /** REQUIRED. Plain string or SchemaLeaf {value, source}.
     *  Enumerates: conda | pip | docker | singularity | nextflow | snakemake | jupyter | native */
    environment_kind?: string | SchemaLeaf | null;
    notes?: string | null;
    /** REQUIRED (non-empty list). */
    entry_points?: EntryPointEntry[];
    /** OPTIONAL */
    dependencies?: {
      runtime?: DependencyEntry[];
      optional?: DependencyEntry[];
      system?: DependencyEntry[];
    };
    /** OPTIONAL */
    containers?: ContainerEntry[];
    /** OPTIONAL */
    compute?: {
      cpu_cores?: SchemaLeaf | null;
      memory_gb?: SchemaLeaf | null;
      gpu_required?: SchemaLeaf | boolean | null;
      parallelism?: string | null;
      typical_runtime?: {
        value?: unknown;
        unit?: string | null;
        source?: string;
        confidence?: string;
      } | null;
      /** Older schema alias for gpu_required */
      gpu?: boolean | null;
      /** Older schema alias for parallelism */
      parallel?: string | null;
    };
    /** OPTIONAL */
    tests?: {
      framework?: string | null;
      invocation?: string | null;
      source?: string;
    };
  };
  io?: {
    inputs?: {
      parameters?: IoParameterEntry[];
      initial_conditions?: IoInitialConditionEntry[];
      data_inputs?: IoDataInputEntry[];
    };
    outputs?: IoOutputEntry[];
    experiment_protocol?: {
      description?: string | null;
      timestep?: {
        value?: unknown;
        unit?: string | null;
        source?: string;
        confidence?: string;
      } | null;
      duration?: {
        value?: unknown;
        unit?: string | null;
        source?: string;
        confidence?: string;
      } | null;
      observables?: string[];
      source?: string;
    };
  };
  provenance?: Record<string, unknown>;
};
