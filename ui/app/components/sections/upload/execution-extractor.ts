import type { ParsedExecutionYaml } from './execution-types';
import type { FormValues, SchemaLeaf } from './metadata-types';

// ── Extract FormValues from parsed execution YAML ─────────────────────────────
// Normalises both schema versions:
//   - status / environment_kind can be a plain string OR a {value,...} SchemaLeaf
//   - language.version is an older alias for language.version_constraint
//   - compute.gpu / compute.parallel are older aliases

export function extractExecutionFormValues(
  parsedExec: ParsedExecutionYaml
): FormValues {
  const values: FormValues = {};
  const exec = parsedExec.execution ?? {};
  const io = parsedExec.io ?? {};
  const prov = parsedExec.provenance ?? {};

  // ── Status ──
  values['execution.status'] = schemaLeafOrString(exec.status);
  values['execution.status.$confidence'] = schemaLeafConfidence(exec.status);

  // ── Language ──
  const lang = exec.language ?? {};
  values['execution.language.name'] = lang.name ?? '';
  // Accept both version_constraint (new) and version (old)
  values['execution.language.version_constraint'] =
    lang.version_constraint ?? lang.version ?? '';

  // ── Environment kind ──
  values['execution.environment_kind'] = schemaLeafOrString(
    exec.environment_kind
  );
  values['execution.environment_kind.$confidence'] = schemaLeafConfidence(
    exec.environment_kind
  );

  // ── Notes ──
  values['execution.notes'] = exec.notes ?? '';

  // ── Entry points (list-entry-point — raw objects passed via getItems) ──
  // Summary string for the collapsed section header
  values['execution.entry_points'] = (exec.entry_points ?? [])
    .map((ep) => ep.command ?? ep.name ?? '')
    .filter(Boolean)
    .join(', ');
  // Per-item editable sub-fields
  for (const [i, ep] of (exec.entry_points ?? []).entries()) {
    values[`execution.entry_points[${i}].command`] = ep.command ?? '';
    values[`execution.entry_points[${i}].purpose`] = ep.purpose ?? '';
    values[`execution.entry_points[${i}].default_output_location`] =
      ep.default_output_location ?? '';
    values[`execution.entry_points[${i}].confidence`] = ep.confidence ?? '';
    values[`execution.entry_points[${i}].source`] = ep.source ?? '';
  }

  // ── Dependencies (list-object) ──
  values['execution.dependencies.runtime'] = (exec.dependencies?.runtime ?? [])
    .map((d) => d.name ?? '')
    .filter(Boolean)
    .join(', ');
  values['execution.dependencies.optional'] = (
    exec.dependencies?.optional ?? []
  )
    .map((d) => d.name ?? '')
    .filter(Boolean)
    .join(', ');
  values['execution.dependencies.system'] = (exec.dependencies?.system ?? [])
    .map((d) => d.name ?? '')
    .filter(Boolean)
    .join(', ');

  // ── Containers (list-container) ──
  values['execution.containers'] = (exec.containers ?? [])
    .map((c) => c.image_name ?? c.file ?? c.kind ?? '')
    .filter(Boolean)
    .join(', ');
  // Per-item editable sub-fields
  for (const [i, c] of (exec.containers ?? []).entries()) {
    values[`execution.containers[${i}].kind`] = c.kind ?? '';
    values[`execution.containers[${i}].file`] = c.file ?? '';
    values[`execution.containers[${i}].image_name`] = c.image_name ?? '';
    values[`execution.containers[${i}].source`] = c.source ?? '';
  }

  // ── Compute ──
  const compute = exec.compute ?? {};

  // gpu_required: SchemaLeaf | boolean | older 'gpu' boolean alias
  const gpuVal =
    compute.gpu_required === undefined ? compute.gpu : compute.gpu_required;
  if (typeof gpuVal === 'boolean') {
    values['execution.compute.gpu_required'] = String(gpuVal);
  } else if (gpuVal !== null && gpuVal !== undefined) {
    // SchemaLeaf shape
    const leaf = gpuVal as SchemaLeaf;
    values['execution.compute.gpu_required'] =
      leaf.value === null || leaf.value === undefined ? '' : String(leaf.value);
    values['execution.compute.gpu_required.$confidence'] = String(
      leaf.confidence ?? ''
    );
  } else {
    values['execution.compute.gpu_required'] = '';
  }

  // cpu_cores: SchemaLeaf
  const cpuLeaf = compute.cpu_cores;
  values['execution.compute.cpu_cores'] =
    cpuLeaf?.value === null || cpuLeaf?.value === undefined
      ? ''
      : String(cpuLeaf.value);
  values['execution.compute.cpu_cores.$confidence'] = String(
    cpuLeaf?.confidence ?? ''
  );

  // memory_gb: SchemaLeaf
  const memLeaf = compute.memory_gb;
  values['execution.compute.memory_gb'] =
    memLeaf?.value === null || memLeaf?.value === undefined
      ? ''
      : String(memLeaf.value);
  values['execution.compute.memory_gb.$confidence'] = String(
    memLeaf?.confidence ?? ''
  );

  // parallelism: plain string | older 'parallel' alias
  values['execution.compute.parallelism'] =
    compute.parallelism ?? compute.parallel ?? '';

  // typical_runtime: { value, unit, source, confidence }
  // Display as a compound "value unit" string (e.g. "60 minutes")
  const rt = compute.typical_runtime;
  if (rt) {
    const rtVal =
      rt.value === null || rt.value === undefined ? '' : String(rt.value);
    const rtUnit = rt.unit ?? '';
    values['execution.compute.typical_runtime'] =
      rtVal && rtUnit ? `${rtVal} ${rtUnit}` : rtVal || rtUnit;
    values['execution.compute.typical_runtime.$confidence'] = String(
      rt.confidence ?? ''
    );
  } else {
    values['execution.compute.typical_runtime'] = '';
  }

  // ── Tests ──
  values['execution.tests.framework'] = exec.tests?.framework ?? '';
  values['execution.tests.invocation'] = exec.tests?.invocation ?? '';

  // ── I/O Inputs (list-object display values) ──
  values['io.inputs.parameters'] = (io.inputs?.parameters ?? [])
    .map((p) => p.name ?? '')
    .filter(Boolean)
    .join(', ');
  values['io.inputs.initial_conditions'] = (io.inputs?.initial_conditions ?? [])
    .map((ic) => ic.name ?? '')
    .filter(Boolean)
    .join(', ');
  values['io.inputs.data_inputs'] = (io.inputs?.data_inputs ?? [])
    .map((di) => di.name ?? '')
    .filter(Boolean)
    .join(', ');

  // ── I/O Outputs ──
  values['io.outputs'] = (io.outputs ?? [])
    .map((o) => o.name ?? '')
    .filter(Boolean)
    .join(', ');

  // ── Protocol ──
  values['io.experiment_protocol.description'] =
    io.experiment_protocol?.description ?? '';
  values['io.experiment_protocol.observables'] = (
    io.experiment_protocol?.observables ?? []
  ).join(', ');

  // ── Provenance (exec_provenance.* prefix) ──
  values['exec_provenance.annotated_at'] = String(prov['annotated_at'] ?? '');
  values['exec_provenance.annotated_by'] = String(prov['annotated_by'] ?? '');
  values['exec_provenance.human_review_required'] = String(
    prov['human_review_required'] ?? ''
  );
  values['exec_provenance.notes'] = String(prov['notes'] ?? '');

  return values;
}

// ── Apply FormValues back into the parsed execution YAML ──────────────────────
// Writes back every field that EXECUTION_TEMPLATE exposes as editable or viewable
// with a toggleable Edit checkbox. Source/confidence on SchemaLeaf fields are
// preserved; only `value` is updated.

export function applyFormValuesToExecution(
  original: ParsedExecutionYaml,
  values: FormValues
): ParsedExecutionYaml {
  const exec = { ...original.execution };

  // ── status ── (editable; may be plain string or SchemaLeaf)
  const newStatus = values['execution.status'] ?? '';
  exec.status =
    exec.status !== null && typeof exec.status === 'object'
      ? { ...exec.status, value: newStatus }
      : newStatus || null;

  // ── language ──
  const langName = values['execution.language.name'];
  const langVC = values['execution.language.version_constraint'];
  exec.language = {
    ...exec.language,
    ...(langName === undefined ? {} : { name: langName || null }),
    ...(langVC === undefined ? {} : { version_constraint: langVC || null }),
  };

  // ── environment_kind ── (may be plain string or SchemaLeaf)
  const envKind = values['execution.environment_kind'];
  if (envKind !== undefined) {
    exec.environment_kind =
      exec.environment_kind !== null &&
      typeof exec.environment_kind === 'object'
        ? { ...exec.environment_kind, value: envKind }
        : envKind || null;
  }

  // ── notes ──
  const notes = values['execution.notes'];
  if (notes !== undefined) {
    exec.notes = notes || null;
  }

  // ── compute ──
  const compute = { ...exec.compute };

  // gpu_required: SchemaLeaf | boolean
  const gpuStr = values['execution.compute.gpu_required'];
  if (gpuStr !== undefined) {
    const gpuFalseOrNull: false | null = gpuStr === 'false' ? false : null;
    const gpuBool: boolean | null = gpuStr === 'true' ? true : gpuFalseOrNull;
    const existing = compute.gpu_required;
    compute.gpu_required =
      existing !== null &&
      existing !== undefined &&
      typeof existing === 'object'
        ? { ...existing, value: gpuBool }
        : gpuBool;
  }

  // cpu_cores: SchemaLeaf — update value, preserve source/confidence
  const cpuStr = values['execution.compute.cpu_cores'];
  if (cpuStr !== undefined) {
    compute.cpu_cores = { ...compute.cpu_cores, value: cpuStr || null };
  }

  // memory_gb: SchemaLeaf — update value, preserve source/confidence
  const memStr = values['execution.compute.memory_gb'];
  if (memStr !== undefined) {
    compute.memory_gb = { ...compute.memory_gb, value: memStr || null };
  }

  // parallelism: plain string
  const parallelism = values['execution.compute.parallelism'];
  if (parallelism !== undefined) {
    compute.parallelism = parallelism || null;
  }

  // typical_runtime: stored as a composite "value unit" display string — we cannot
  // cleanly split it back, so we leave the original object untouched.

  exec.compute = compute as typeof exec.compute;

  // ── tests ──
  const framework = values['execution.tests.framework'];
  const invocation = values['execution.tests.invocation'];
  exec.tests = {
    ...exec.tests,
    ...(framework === undefined ? {} : { framework: framework || null }),
    ...(invocation === undefined ? {} : { invocation: invocation || null }),
  };

  // ── containers (per-item) ──
  if (Array.isArray(exec.containers)) {
    exec.containers = exec.containers.map((c, i) => {
      const kind = values[`execution.containers[${i}].kind`];
      const file = values[`execution.containers[${i}].file`];
      const image_name = values[`execution.containers[${i}].image_name`];
      const source = values[`execution.containers[${i}].source`];
      return {
        ...c,
        ...(kind === undefined ? {} : { kind: kind || null }),
        ...(file === undefined ? {} : { file: file || null }),
        ...(image_name === undefined ? {} : { image_name: image_name || null }),
        ...(source === undefined ? {} : { source: source || undefined }),
      };
    });
  }

  // ── entry points (per-item) ──
  if (Array.isArray(exec.entry_points)) {
    exec.entry_points = exec.entry_points.map((ep, i) => {
      const command = values[`execution.entry_points[${i}].command`];
      const purpose = values[`execution.entry_points[${i}].purpose`];
      const loc =
        values[`execution.entry_points[${i}].default_output_location`];
      const confidence = values[`execution.entry_points[${i}].confidence`];
      return {
        ...ep,
        ...(command === undefined ? {} : { command: command || null }),
        ...(purpose === undefined ? {} : { purpose: purpose || null }),
        ...(loc === undefined ? {} : { default_output_location: loc || null }),
        ...(confidence === undefined ? {} : { confidence: confidence || null }),
      };
    });
  }

  // ── io.experiment_protocol ──
  const io = { ...original.io };
  const protocolDesc = values['io.experiment_protocol.description'];
  const protocolObs = values['io.experiment_protocol.observables'];
  if (protocolDesc !== undefined || protocolObs !== undefined) {
    io.experiment_protocol = {
      ...io.experiment_protocol,
      ...(protocolDesc === undefined
        ? {}
        : { description: protocolDesc || null }),
      ...(protocolObs === undefined
        ? {}
        : {
            observables: protocolObs
              ? protocolObs
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
              : [],
          }),
    };
  }

  return { ...original, execution: exec, io };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Extracts a display string from a field that may be a plain string or SchemaLeaf. */
function schemaLeafOrString(
  field: string | { value?: unknown } | null | undefined
): string {
  if (field === null || field === undefined) return '';
  if (typeof field === 'string') return field;
  if (typeof field === 'object' && 'value' in field) {
    return field.value === null || field.value === undefined
      ? ''
      : String(field.value);
  }
  return '';
}

/** Extracts the confidence string from a SchemaLeaf (returns '' for plain strings). */
function schemaLeafConfidence(
  field: string | { confidence?: unknown } | null | undefined
): string {
  if (field === null || field === undefined || typeof field === 'string')
    return '';
  if (typeof field === 'object' && 'confidence' in field) {
    return field.confidence === null || field.confidence === undefined
      ? ''
      : String(field.confidence);
  }
  return '';
}
