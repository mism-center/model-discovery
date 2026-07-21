import type { AnnotationTemplate } from './metadata-types';

/**
 * Source-of-truth field annotation template for execution.yaml.
 *
 * Keys are dotted paths into the parsed YAML structure.
 * Fields absent from this template are not rendered.
 *
 * Visibility:
 *   'editable' → renders as a pre-populated text input or textarea
 *   'viewable' → renders as a read-only label+value display
 *
 * Note: provenance keys use the 'exec_provenance.' prefix to avoid
 * collision with metadata.yaml provenance keys in shared form state.
 */
export const EXECUTION_TEMPLATE: AnnotationTemplate = {
  // ── Overview ──────────────────────────────────────────────────────────────

  'execution.status': {
    label: 'Status',
    visibility: 'viewable',
    inputType: 'text',
    required: true,
    hidden: false,
    forceReadOnly: true,
    description: 'characterized | partially_characterized | not_determined',
  },
  'execution.language.name': {
    label: 'Language',
    visibility: 'viewable',
    inputType: 'text',
    required: true,
    hidden: false,
    description: 'Primary programming language',
  },
  'execution.language.version_constraint': {
    label: 'Version Constraint',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    description: 'Language version requirement (e.g. >=3.10,<3.13)',
  },
  'execution.environment_kind': {
    label: 'Environment Kind',
    visibility: 'viewable',
    inputType: 'text',
    required: true,
    hidden: false,
    description:
      'conda | pip | docker | singularity | nextflow | snakemake | jupyter | native',
  },
  'execution.notes': {
    label: 'Notes',
    visibility: 'viewable',
    inputType: 'textarea',
    hidden: false,
  },

  // ── Entry Points ──────────────────────────────────────────────────────────

  'execution.entry_points': {
    label: 'Entry Points',
    visibility: 'viewable',
    inputType: 'list-entry-point',
    required: true,
    hidden: false,
    description: 'Commands used to invoke the model',
  },

  // ── Dependencies ──────────────────────────────────────────────────────────

  'execution.dependencies.runtime': {
    label: 'Runtime Dependencies',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },
  'execution.dependencies.optional': {
    label: 'Optional Dependencies',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },
  'execution.dependencies.system': {
    label: 'System Dependencies',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
    description: 'OS-level packages (apt, brew, BLAS, MPI, CUDA toolkit)',
  },

  // ── Containers ────────────────────────────────────────────────────────────

  'execution.containers': {
    label: 'Containers',
    visibility: 'viewable',
    inputType: 'list-container',
    hidden: false,
    description: 'Docker or Singularity container definitions',
  },

  // ── Compute ───────────────────────────────────────────────────────────────

  'execution.compute.gpu_required': {
    label: 'GPU Required',
    visibility: 'viewable',
    inputType: 'boolean',
    hidden: false,
  },
  'execution.compute.cpu_cores': {
    label: 'CPU Cores',
    visibility: 'viewable',
    inputType: 'object-scalar',
    hidden: false,
  },
  'execution.compute.memory_gb': {
    label: 'Memory (GB)',
    visibility: 'viewable',
    inputType: 'object-scalar',
    hidden: false,
  },
  'execution.compute.parallelism': {
    label: 'Parallelism',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    description:
      'single | multi-thread | multi-process | MPI | GPU | distributed',
  },
  'execution.compute.typical_runtime': {
    label: 'Typical Runtime',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    description: 'Estimated wall-clock time for a typical run',
  },

  // ── Tests ─────────────────────────────────────────────────────────────────

  'execution.tests.framework': {
    label: 'Test Framework',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    description: 'e.g. pytest, unittest, Test.jl',
  },
  'execution.tests.invocation': {
    label: 'Test Invocation',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
    description: 'Command used to run the test suite',
  },

  // ── I/O — Inputs ──────────────────────────────────────────────────────────

  'io.inputs.parameters': {
    label: 'Parameters',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
    description: 'Scalar / array configuration inputs',
  },
  'io.inputs.initial_conditions': {
    label: 'Initial Conditions',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },
  'io.inputs.data_inputs': {
    label: 'Data Inputs',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
    description: 'External file or data dependencies',
  },

  // ── I/O — Outputs ─────────────────────────────────────────────────────────

  'io.outputs': {
    label: 'Outputs',
    visibility: 'viewable',
    inputType: 'list-object',
    hidden: false,
  },

  // ── Protocol ──────────────────────────────────────────────────────────────

  'io.experiment_protocol.description': {
    label: 'Protocol Description',
    visibility: 'viewable',
    inputType: 'textarea',
    hidden: false,
  },
  'io.experiment_protocol.observables': {
    label: 'Observables',
    visibility: 'viewable',
    inputType: 'list-scalar',
    hidden: false,
    description: 'Quantities recorded during a run',
  },

  // ── Provenance ────────────────────────────────────────────────────────────
  // Keys use 'exec_provenance.' prefix to avoid collision with metadata provenance.

  'exec_provenance.annotated_at': {
    label: 'Annotated At',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
  },
  'exec_provenance.annotated_by': {
    label: 'Annotated By',
    visibility: 'viewable',
    inputType: 'text',
    hidden: false,
  },
  'exec_provenance.human_review_required': {
    label: 'Human Review Required',
    visibility: 'viewable',
    inputType: 'boolean',
    hidden: false,
  },
  'exec_provenance.notes': {
    label: 'Notes',
    visibility: 'viewable',
    inputType: 'static',
    hidden: false,
  },
};
