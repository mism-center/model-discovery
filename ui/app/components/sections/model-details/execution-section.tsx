import type { ModelDetailResponse } from '~/api/endpoints/models';
import {
  Field,
  SectionAbsence,
  SectionCard,
  SubHeading,
  type Subsection,
  hasItems,
  hasValue,
} from './primitives';

type Compute = NonNullable<ModelDetailResponse['compute']>;

/**
 * Flatten compute requirements into label/value rows.
 *
 * Lifted out of the grid so the section can ask whether compute has anything to
 * show before deciding it is empty — `compute` is often a present-but-blank
 * object.
 */
function computeRows(
  compute: Compute | null | undefined
): Array<[string, string]> {
  if (!compute) return [];

  const rows: Array<[string, string]> = [];
  if (typeof compute.cpu_cores === 'number')
    rows.push(['CPU cores', String(compute.cpu_cores)]);
  if (typeof compute.memory_gb === 'number')
    rows.push(['Memory', `${compute.memory_gb} GB`]);
  if (compute.gpu_required !== null && compute.gpu_required !== undefined)
    rows.push(['GPU', compute.gpu_required ? 'Required' : 'Not required']);
  if (compute.parallelism) rows.push(['Parallelism', compute.parallelism]);
  if (typeof compute.typical_runtime === 'number') {
    rows.push([
      'Typical runtime',
      `${compute.typical_runtime} ${compute.typical_runtime_unit || ''}`.trim(),
    ]);
  }
  return rows;
}

function hasTests(tests: ModelDetailResponse['tests']): boolean {
  return Boolean(tests && (tests.framework || tests.invocation));
}

/**
 * Runtime environment, dependencies and compute requirements (schema.md
 * Section B).
 *
 * Every field here defaults to `''`, `[]` or `None` server-side, so for a
 * dataset or an un-characterized model all of them are absent at once — hence
 * the explicit empty body rather than a grid that would render nothing under the
 * heading.
 *
 * Does not show `execution_status`. Its values (`characterized`,
 * `partially_characterized`, `not_determined`) describe how completely a curator
 * filled this section in, not anything about the model — and the section already
 * shows that structurally, by having fields or saying it has none.
 */
export function ExecutionSection({ model }: { model: ModelDetailResponse }) {
  const language = [model.language_name, model.language_version]
    .filter(Boolean)
    .join(' ');
  const compute = computeRows(model.compute);

  const hasContent =
    Boolean(language) ||
    hasValue(model.execution_type) ||
    hasValue(model.execution_notes) ||
    compute.length > 0 ||
    hasItems(model.dependencies) ||
    hasItems(model.containers) ||
    hasItems(model.entry_points) ||
    hasTests(model.tests);

  if (!hasContent) {
    return (
      <SectionCard
        title="Execution"
        description="Runtime environment, dependencies, and compute requirements."
      >
        <SectionAbsence>
          No execution environment has been recorded, so this model cannot be
          run from the portal.
        </SectionAbsence>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title="Execution"
      description="Runtime environment, dependencies, and compute requirements."
    >
      <dl className="grid gap-5 sm:grid-cols-2">
        {language && <Field label="Language">{language}</Field>}
        {hasValue(model.execution_type) && (
          <Field label="Environment">{model.execution_type}</Field>
        )}
      </dl>

      {model.execution_notes && (
        <p className="mt-4 text-sm text-default-900 leading-relaxed">
          {model.execution_notes}
        </p>
      )}

      {EXECUTION_BLOCKS.filter((block) => block.present(model)).map((block) => (
        <div key={block.id} className="mt-6">
          <SubHeading id={block.id}>{block.label}</SubHeading>
          {block.render(model)}
        </div>
      ))}
    </SectionCard>
  );
}

/**
 * The subheaded blocks of this section, in render order. One list drives both the
 * rendered subheadings and the nav's subsection entries — see `IO_BLOCKS` for why
 * the nav needs these from data rather than from the DOM.
 *
 * The Language/Environment grid and execution notes above are deliberately not
 * here: they carry no subheading, so there is nothing to anchor to.
 */
const EXECUTION_BLOCKS: Array<
  Subsection & {
    present: (model: ModelDetailResponse) => boolean;
    render: (model: ModelDetailResponse) => React.ReactNode;
  }
> = [
  {
    id: 'compute-requirements',
    label: 'Compute requirements',
    present: (model) => computeRows(model.compute).length > 0,
    render: (model) => (
      <dl className="grid gap-4 sm:grid-cols-3">
        {computeRows(model.compute).map(([label, value]) => (
          <Field key={label} label={label}>
            {value}
          </Field>
        ))}
      </dl>
    ),
  },
  {
    id: 'dependencies',
    label: 'Dependencies',
    present: (model) => hasItems(model.dependencies),
    render: (model) => <DependenciesBody dependencies={model.dependencies} />,
  },
  {
    id: 'containers',
    label: 'Containers',
    present: (model) => hasItems(model.containers),
    render: (model) => (
      <ul className="flex flex-col gap-2">
        {(model.containers ?? []).map((c, i) => (
          <li
            key={`${c.kind}-${c.image_name || c.file || i}`}
            className="text-sm text-default-900"
          >
            <span className="font-semibold capitalize">{c.kind}</span>
            {c.image_name && (
              <span className="font-mono"> · {c.image_name}</span>
            )}
            {c.file && <span className="text-default-800"> ({c.file})</span>}
          </li>
        ))}
      </ul>
    ),
  },
  {
    id: 'entry-points',
    label: 'Entry points',
    present: (model) => hasItems(model.entry_points),
    render: (model) => <EntryPointsBody entryPoints={model.entry_points} />,
  },
  {
    id: 'tests',
    label: 'Tests',
    present: (model) => hasTests(model.tests),
    render: (model) => (
      <p className="text-sm text-default-900">
        {model.tests?.framework && (
          <span className="font-semibold">{model.tests.framework}</span>
        )}
        {model.tests?.invocation && (
          <code className="ml-2 rounded bg-default-100 px-1.5 py-0.5 font-mono text-xs">
            {model.tests.invocation}
          </code>
        )}
      </p>
    ),
  },
];

/** Subsection entries for whichever execution blocks this model populates. */
export function executionSubsections(model: ModelDetailResponse): Subsection[] {
  return EXECUTION_BLOCKS.filter((block) => block.present(model)).map(
    ({ id, label }) => ({ id, label })
  );
}

function DependenciesBody({
  dependencies,
}: {
  dependencies: ModelDetailResponse['dependencies'];
}) {
  const byKind = new Map<string, NonNullable<typeof dependencies>>();
  for (const d of dependencies ?? []) {
    const kind = d.kind || 'runtime';
    const list = byKind.get(kind) ?? [];
    list.push(d);
    byKind.set(kind, list);
  }

  return (
    <div className="flex flex-col gap-3">
      {[...byKind.entries()].map(([kind, deps]) => (
        <div key={kind}>
          <p className="text-sm font-semibold text-default-900 capitalize mb-1">
            {kind}
          </p>
          <ul className="flex flex-wrap gap-x-4 gap-y-1">
            {deps.map((d) => (
              <li
                key={`${d.name}-${d.group}`}
                className="text-sm font-mono text-default-900"
              >
                {d.name}
                {d.version_constraint && (
                  <span className="text-default-800">
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
  );
}

function EntryPointsBody({
  entryPoints,
}: {
  entryPoints: ModelDetailResponse['entry_points'];
}) {
  return (
    <ul className="flex flex-col gap-3">
      {(entryPoints ?? []).map((e, i) => (
        <li key={`${e.command}-${i}`}>
          <code className="block rounded bg-default-100 px-2 py-1 font-mono text-xs text-default-900">
            {e.command}
          </code>
          {e.purpose && (
            <p className="mt-1 text-sm text-default-900">{e.purpose}</p>
          )}
          {hasItems(e.arguments) && (
            <ul className="mt-1 ml-3 flex flex-col gap-0.5">
              {e.arguments.map((a) => (
                <li key={a.name} className="text-xs text-default-900">
                  <span className="font-mono">{a.name}</span>
                  {a.description && <span> — {a.description}</span>}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}
