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
  values['execution.language.iri'] = lang.iri ?? '';
  values['execution.language.ontology'] = lang.ontology ?? '';

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
    // Per-argument sub-fields
    for (const [j, arg] of (ep.arguments ?? []).entries()) {
      values[`execution.entry_points[${i}].arguments[${j}].name`] =
        arg.name ?? '';
      values[`execution.entry_points[${i}].arguments[${j}].description`] =
        arg.description ?? '';
      values[`execution.entry_points[${i}].arguments[${j}].default`] =
        arg.default === null || arg.default === undefined
          ? ''
          : String(arg.default);
      values[`execution.entry_points[${i}].arguments[${j}].data_type`] =
        arg.data_type ?? '';
      values[
        `execution.entry_points[${i}].arguments[${j}].user_can_override`
      ] =
        arg.user_can_override === null || arg.user_can_override === undefined
          ? ''
          : String(arg.user_can_override);
    }
  }

  // ── Dependencies (list-dep — per-item name/version_constraint/source) ──
  for (const kind of ['runtime', 'optional', 'system'] as const) {
    const deps = exec.dependencies?.[kind] ?? [];
    values[`execution.dependencies.${kind}`] = deps
      .map((d) => d.name ?? '')
      .filter(Boolean)
      .join(', ');
    for (const [i, d] of deps.entries()) {
      values[`execution.dependencies.${kind}[${i}].name`] = d.name ?? '';
      values[`execution.dependencies.${kind}[${i}].version_constraint`] =
        d.version_constraint ?? '';
      values[`execution.dependencies.${kind}[${i}].source`] = d.source ?? '';
    }
  }

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
  // timestep and duration: display as "value unit" compound strings
  const ts = io.experiment_protocol?.timestep;
  values['io.experiment_protocol.timestep'] = ts
    ? [ts.value, ts.unit].filter(Boolean).join(' ')
    : '';
  const dur = io.experiment_protocol?.duration;
  values['io.experiment_protocol.duration'] = dur
    ? [dur.value, dur.unit].filter(Boolean).join(' ')
    : '';
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

  // ── containers (per-item, form-value-count-based to support added items) ──
  const containerCount = countFormItems(values, 'execution.containers', 'kind');
  if (containerCount > 0 || Array.isArray(exec.containers)) {
    exec.containers = Array.from({ length: containerCount }, (_, i) => {
      const existing = (exec.containers ?? [])[i] ?? {};
      return {
        ...existing,
        kind:
          values[`execution.containers[${i}].kind`] ?? existing.kind ?? null,
        file:
          values[`execution.containers[${i}].file`] ?? existing.file ?? null,
        image_name:
          values[`execution.containers[${i}].image_name`] ??
          existing.image_name ??
          null,
        source:
          values[`execution.containers[${i}].source`] ??
          existing.source ??
          undefined,
      };
    });
  }

  // ── entry points (per-item, form-value-count-based to support added items) ──
  const epCount = countFormItems(values, 'execution.entry_points', 'command');
  if (epCount > 0 || Array.isArray(exec.entry_points)) {
    exec.entry_points = Array.from({ length: epCount }, (_, i) => {
      const existing = (exec.entry_points ?? [])[i] ?? {};
      return {
        ...existing,
        command:
          values[`execution.entry_points[${i}].command`] ??
          existing.command ??
          null,
        purpose:
          values[`execution.entry_points[${i}].purpose`] ??
          existing.purpose ??
          null,
        default_output_location:
          values[`execution.entry_points[${i}].default_output_location`] ??
          existing.default_output_location ??
          null,
        confidence:
          values[`execution.entry_points[${i}].confidence`] ??
          existing.confidence ??
          null,
        arguments: (() => {
          const argCount = countFormItems(
            values,
            `execution.entry_points[${i}].arguments`,
            'name'
          );
          if (argCount === 0 && !Array.isArray(existing.arguments)) {
            return existing.arguments;
          }
          return Array.from({ length: argCount }, (_, j) => {
            const existingArg = (existing.arguments ?? [])[j] ?? {};
            const dataType =
              values[
                `execution.entry_points[${i}].arguments[${j}].data_type`
              ] ??
              existingArg.data_type ??
              '';
            const rawDefault =
              values[
                `execution.entry_points[${i}].arguments[${j}].default`
              ];
            let parsedDefault: unknown = existingArg.default;
            if (rawDefault !== undefined) {
              if (dataType === 'bool') {
                parsedDefault =
                  rawDefault === 'true'
                    ? true
                    : rawDefault === 'false'
                      ? false
                      : null;
              } else if (dataType === 'int') {
                const n = parseInt(rawDefault, 10);
                parsedDefault = isNaN(n) ? null : n;
              } else if (dataType === 'float') {
                const n = parseFloat(rawDefault);
                parsedDefault = isNaN(n) ? null : n;
              } else {
                parsedDefault = rawDefault || null;
              }
            }
            const rawUco =
              values[
                `execution.entry_points[${i}].arguments[${j}].user_can_override`
              ];
            const parsedUco: boolean | null | undefined =
              rawUco === 'true'
                ? true
                : rawUco === 'false'
                  ? false
                  : rawUco === undefined
                    ? existingArg.user_can_override
                    : null;
            return {
              ...existingArg,
              name:
                values[
                  `execution.entry_points[${i}].arguments[${j}].name`
                ] ??
                existingArg.name ??
                null,
              description:
                values[
                  `execution.entry_points[${i}].arguments[${j}].description`
                ] ??
                existingArg.description ??
                null,
              default: parsedDefault,
              data_type: dataType || null,
              user_can_override: parsedUco,
            };
          });
        })(),
      };
    });
  }

  // ── dependencies (per-item, form-value-count-based) ──
  const deps = { ...exec.dependencies };
  for (const kind of ['runtime', 'optional', 'system'] as const) {
    const count = countFormItems(
      values,
      `execution.dependencies.${kind}`,
      'name'
    );
    if (count > 0 || Array.isArray(deps[kind])) {
      deps[kind] = Array.from({ length: count }, (_, i) => {
        const existing = (deps[kind] ?? [])[i] ?? {};
        return {
          ...existing,
          name:
            values[`execution.dependencies.${kind}[${i}].name`] ??
            existing.name ??
            null,
          version_constraint:
            values[`execution.dependencies.${kind}[${i}].version_constraint`] ??
            existing.version_constraint ??
            null,
          source:
            values[`execution.dependencies.${kind}[${i}].source`] ??
            existing.source ??
            undefined,
        };
      });
    }
  }
  exec.dependencies = deps as typeof exec.dependencies;

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

/**
 * Counts how many items exist in formValues for a given list field key,
 * using the presence of `${fieldKey}[i].${primarySubfield}` as the probe.
 * This lets write-back handle items added via the UI (beyond the original YAML).
 */
function countFormItems(
  values: FormValues,
  fieldKey: string,
  primarySubfield: string
): number {
  let i = 0;
  while (`${fieldKey}[${i}].${primarySubfield}` in values) i++;
  return i;
}
