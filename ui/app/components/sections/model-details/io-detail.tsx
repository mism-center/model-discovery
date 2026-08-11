import type { ModelDetailResponse } from '~/api/endpoints/models';
import { AbsentCell, Chip, SubHeading, type Subsection } from './primitives';

type IODetail = NonNullable<ModelDetailResponse['io']>;

function hasRows(rows: unknown[] | null | undefined): boolean {
  return Boolean(rows && rows.length > 0);
}

function protocolHasContent(io: IODetail): boolean {
  const p = io.experiment_protocol;
  if (!p) return false;
  return Boolean(
    p.description ||
    typeof p.timestep === 'number' ||
    typeof p.duration === 'number' ||
    hasRows(p.observables)
  );
}

/**
 * The blocks of the I/O characterization, in render order.
 *
 * One list drives both the rendered subheadings and the nav's subsection
 * entries, so the two cannot disagree about which blocks this model has. The nav
 * needs them derived from data rather than from the DOM: a collapsed section
 * unmounts its subheadings, but its entries must stay listed so they can be
 * jumped to.
 */
const IO_BLOCKS: Array<
  Subsection & {
    present: (io: IODetail) => boolean;
    render: (io: IODetail) => React.ReactNode;
  }
> = [
  {
    id: 'parameters',
    label: 'Parameters',
    present: (io) => hasRows(io.parameters),
    render: (io) => (
      <DataTable
        columns={['Name', 'Default', 'Unit', 'Meaning']}
        rows={(io.parameters ?? []).map((p) => [
          <span key="n" className="font-mono">
            {p.name}
          </span>,
          formatValue(p.default_value),
          p.unit || <AbsentCell />,
          p.biological_meaning || p.description || <AbsentCell />,
        ])}
      />
    ),
  },
  {
    id: 'initial-conditions',
    label: 'Initial conditions',
    present: (io) => hasRows(io.initial_conditions),
    render: (io) => (
      <DataTable
        columns={['Name', 'Value', 'Unit']}
        rows={(io.initial_conditions ?? []).map((c) => [
          <span key="n" className="font-mono">
            {c.name}
          </span>,
          formatValue(c.value),
          c.unit || <AbsentCell />,
        ])}
      />
    ),
  },
  {
    id: 'data-inputs',
    label: 'Data inputs',
    present: (io) => hasRows(io.data_inputs),
    render: (io) => (
      <DataTable
        columns={['Name', 'Format', 'Required', 'Purpose']}
        rows={(io.data_inputs ?? []).map((d) => [
          <span key="n" className="font-mono">
            {d.name}
          </span>,
          d.format || <AbsentCell />,
          d.required ? 'Required' : 'Optional',
          d.purpose || <AbsentCell />,
        ])}
      />
    ),
  },
  {
    id: 'outputs',
    label: 'Outputs',
    present: (io) => hasRows(io.outputs),
    render: (io) => (
      <DataTable
        columns={['Name', 'Quantity', 'Unit', 'Format']}
        rows={(io.outputs ?? []).map((o) => [
          <span key="n" className="font-mono">
            {o.name}
          </span>,
          o.quantity_kind || o.description || <AbsentCell />,
          o.unit || <AbsentCell />,
          o.format || <AbsentCell />,
        ])}
      />
    ),
  },
  {
    id: 'experiment-protocol',
    label: 'Experiment protocol',
    present: protocolHasContent,
    render: (io) =>
      io.experiment_protocol ? (
        <ProtocolBody protocol={io.experiment_protocol} />
      ) : null,
  },
];

/** Subsection entries for whichever I/O blocks this model populates. */
export function ioDetailSubsections(
  io: IODetail | null | undefined
): Subsection[] {
  if (!io) return [];
  return IO_BLOCKS.filter((block) => block.present(io)).map(
    ({ id, label }) => ({
      id,
      label,
    })
  );
}

/**
 * The model's I/O characterization (schema.md Section C) rendered for humans:
 * real names, units, defaults and biological meaning, laid out as tables.
 */
export function IODetailBlocks({ io }: { io: IODetail | null | undefined }) {
  if (!io) return null;

  return (
    <div className="flex flex-col gap-6">
      {IO_BLOCKS.filter((block) => block.present(io)).map((block) => (
        <div key={block.id}>
          <SubHeading id={block.id}>{block.label}</SubHeading>
          {block.render(io)}
        </div>
      ))}
    </div>
  );
}

function ProtocolBody({
  protocol,
}: {
  protocol: NonNullable<IODetail['experiment_protocol']>;
}) {
  const timestep = joinQuantity(protocol.timestep, protocol.timestep_unit);
  const duration = joinQuantity(protocol.duration, protocol.duration_unit);
  const observables = protocol.observables ?? [];

  return (
    <>
      {protocol.description && (
        <p className="text-sm text-default-900 mb-3">{protocol.description}</p>
      )}
      <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-default-900">
        {timestep && (
          <span>
            <span className="font-semibold">Timestep:</span> {timestep}
          </span>
        )}
        {duration && (
          <span>
            <span className="font-semibold">Duration:</span> {duration}
          </span>
        )}
      </div>
      {observables.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {observables.map((o) => (
            <Chip key={o} tone="neutral">
              {o}
            </Chip>
          ))}
        </div>
      )}
    </>
  );
}

/**
 * A compact data table. Wrapped in its own `overflow-x-auto` so a wide table
 * scrolls itself rather than forcing the page to scroll sideways.
 */
function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-default-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-default-50 text-left">
            {columns.map((c) => (
              <th
                key={c}
                scope="col"
                className="px-3 py-2 text-xs font-bold uppercase tracking-wider text-default-800 whitespace-nowrap"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-default-200">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-primary/4">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 align-top text-default-900">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Render an arbitrary JSON default without leaking `[object Object]`. */
function formatValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined || value === '') {
    return <AbsentCell />;
  }
  if (typeof value === 'object') {
    return <code className="font-mono">{JSON.stringify(value)}</code>;
  }
  return <span className="font-mono">{String(value)}</span>;
}

function joinQuantity(
  value: number | null | undefined,
  unit: string | null | undefined
): string {
  if (typeof value !== 'number') return '';
  return `${value} ${unit || ''}`.trim();
}
