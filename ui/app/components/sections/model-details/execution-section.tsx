import type { ModelDetailResponse } from '~/api/endpoints/models';
import { SectionCard, Field, ChipList } from './primitives';

/**
 * Execution characterization (schema.md Section B) + model characterization
 * (Section A) + biology. These fields come from the metadata-package workflow
 * and are frequently empty, so each block only renders when it has content.
 */
export function ExecutionSection({ model }: { model: ModelDetailResponse }) {
  return (
    <>
      <ModelCharacterization model={model} />
      <ExecutionCharacterization model={model} />
      <Biology model={model} />
    </>
  );
}

function hasAny(...values: unknown[]): boolean {
  return values.some((v) =>
    Array.isArray(v) ? v.length > 0 : v !== null && v !== undefined && v !== ''
  );
}

/** Render a nullable boolean as Yes / No / — (unknown). */
function formatTristate(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value ? 'Yes' : 'No';
}

function ModelCharacterization({ model }: { model: ModelDetailResponse }) {
  const show = hasAny(
    model.model_class,
    model.formalism,
    model.multiscale,
    model.determinism === 'unknown' ? '' : model.determinism,
    model.time_dynamics === 'unknown' ? '' : model.time_dynamics,
    model.spatial === 'unknown' ? '' : model.spatial
  );
  if (!show) return null;

  return (
    <SectionCard
      title="Model characterization"
      description="How this model is classified mathematically and dynamically."
    >
      <dl className="grid gap-5 sm:grid-cols-2">
        <Field label="Model class">
          <ChipList values={model.model_class} tone="neutral" />
        </Field>
        <Field label="Formalism">
          <ChipList values={model.formalism} tone="neutral" />
        </Field>
        <Field label="Determinism">{model.determinism}</Field>
        <Field label="Time dynamics">{model.time_dynamics}</Field>
        <Field label="Spatial">{model.spatial}</Field>
        <Field label="Multiscale">{formatTristate(model.multiscale)}</Field>
      </dl>
    </SectionCard>
  );
}

function ExecutionCharacterization({ model }: { model: ModelDetailResponse }) {
  const show = hasAny(
    model.language_name,
    model.execution_status,
    model.execution_notes,
    model.dependencies,
    model.containers,
    model.compute,
    model.entry_points,
    model.tests
  );
  if (!show) return null;

  const language = [model.language_name, model.language_version]
    .filter(Boolean)
    .join(' ');

  return (
    <SectionCard
      title="Execution"
      description="Runtime environment, dependencies, and compute requirements."
    >
      <dl className="grid gap-5 sm:grid-cols-2">
        {language && <Field label="Language">{language}</Field>}
        {model.execution_status && (
          <Field label="Characterization status">
            {model.execution_status.replaceAll('_', ' ')}
          </Field>
        )}
        {model.execution_type && (
          <Field label="Environment">{model.execution_type}</Field>
        )}
      </dl>

      {model.execution_notes && (
        <p className="mt-4 text-[13px] text-default-700 leading-relaxed">
          {model.execution_notes}
        </p>
      )}

      {model.compute && <ComputeGrid compute={model.compute} />}

      {model.dependencies && model.dependencies.length > 0 && (
        <Dependencies dependencies={model.dependencies} />
      )}

      {model.containers && model.containers.length > 0 && (
        <div className="mt-6">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-default-600 mb-2">
            Containers
          </h3>
          <ul className="flex flex-col gap-2">
            {model.containers.map((c, i) => (
              <li
                key={`${c.kind}-${c.image_name || c.file || i}`}
                className="text-[13px] text-default-900"
              >
                <span className="font-semibold capitalize">{c.kind}</span>
                {c.image_name && (
                  <span className="font-mono"> · {c.image_name}</span>
                )}
                {c.file && (
                  <span className="text-default-600"> ({c.file})</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {model.entry_points && model.entry_points.length > 0 && (
        <EntryPoints entryPoints={model.entry_points} />
      )}

      {model.tests && (model.tests.framework || model.tests.invocation) && (
        <div className="mt-6">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-default-600 mb-2">
            Tests
          </h3>
          <p className="text-[13px] text-default-900">
            {model.tests.framework && (
              <span className="font-semibold">{model.tests.framework}</span>
            )}
            {model.tests.invocation && (
              <code className="ml-2 rounded bg-default-100 px-1.5 py-0.5 font-mono text-[12px]">
                {model.tests.invocation}
              </code>
            )}
          </p>
        </div>
      )}
    </SectionCard>
  );
}

function ComputeGrid({
  compute,
}: {
  compute: NonNullable<ModelDetailResponse['compute']>;
}) {
  const runtime =
    typeof compute.typical_runtime === 'number'
      ? `${compute.typical_runtime} ${compute.typical_runtime_unit || ''}`.trim()
      : undefined;

  const rows: Array<[string, string]> = [];
  if (typeof compute.cpu_cores === 'number')
    rows.push(['CPU cores', String(compute.cpu_cores)]);
  if (typeof compute.memory_gb === 'number')
    rows.push(['Memory', `${compute.memory_gb} GB`]);
  if (compute.gpu_required !== null && compute.gpu_required !== undefined)
    rows.push(['GPU', compute.gpu_required ? 'Required' : 'Not required']);
  if (compute.parallelism) rows.push(['Parallelism', compute.parallelism]);
  if (runtime) rows.push(['Typical runtime', runtime]);

  if (rows.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-default-600 mb-2">
        Compute requirements
      </h3>
      <dl className="grid gap-4 sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <Field key={label} label={label}>
            {value}
          </Field>
        ))}
      </dl>
    </div>
  );
}

function Dependencies({
  dependencies,
}: {
  dependencies: NonNullable<ModelDetailResponse['dependencies']>;
}) {
  const byKind = new Map<string, typeof dependencies>();
  for (const d of dependencies) {
    const kind = d.kind || 'runtime';
    const list = byKind.get(kind) ?? [];
    list.push(d);
    byKind.set(kind, list);
  }

  return (
    <div className="mt-6">
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-default-600 mb-2">
        Dependencies
      </h3>
      <div className="flex flex-col gap-3">
        {[...byKind.entries()].map(([kind, deps]) => (
          <div key={kind}>
            <p className="text-[12px] font-semibold text-default-700 capitalize mb-1">
              {kind}
            </p>
            <ul className="flex flex-wrap gap-x-4 gap-y-1">
              {deps.map((d) => (
                <li
                  key={`${d.name}-${d.group}`}
                  className="text-[13px] font-mono text-default-900"
                >
                  {d.name}
                  {d.version_constraint && (
                    <span className="text-default-600">
                      {' '}
                      {d.version_constraint}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function EntryPoints({
  entryPoints,
}: {
  entryPoints: NonNullable<ModelDetailResponse['entry_points']>;
}) {
  return (
    <div className="mt-6">
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-default-600 mb-2">
        Entry points
      </h3>
      <ul className="flex flex-col gap-3">
        {entryPoints.map((e, i) => (
          <li key={`${e.command}-${i}`}>
            <code className="block rounded bg-default-100 px-2 py-1 font-mono text-[12px] text-default-900">
              {e.command}
            </code>
            {e.purpose && (
              <p className="mt-1 text-[13px] text-default-700">{e.purpose}</p>
            )}
            {e.arguments && e.arguments.length > 0 && (
              <ul className="mt-1 ml-3 flex flex-col gap-0.5">
                {e.arguments.map((a) => (
                  <li key={a.name} className="text-[12px] text-default-700">
                    <span className="font-mono">{a.name}</span>
                    {a.description && <span> — {a.description}</span>}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Biology({ model }: { model: ModelDetailResponse }) {
  const show = hasAny(
    model.infectious_agents,
    model.health_conditions,
    model.biological_processes,
    model.molecular_entities,
    model.proteins_genes
  );
  if (!show) return null;

  return (
    <SectionCard
      title="Biology"
      description="Biological entities and processes this model represents."
    >
      <dl className="grid gap-5 sm:grid-cols-2">
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
    </SectionCard>
  );
}
