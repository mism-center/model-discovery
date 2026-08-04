import type { ModelDetailResponse } from '~/api/endpoints/models';
import { Chip, NotRecorded, SubHeading } from './primitives';

type IODetail = NonNullable<ModelDetailResponse['io']>;

/**
 * The model's I/O characterization (schema.md Section C) rendered for humans.
 *
 * This is the data that replaces the old `JSON.stringify(parameters_schema)`
 * dump: real names, units, defaults and biological meaning, laid out as tables.
 * `io_spec` (slot names + a JSON Schema) is the machine handshake used to
 * validate a run; it is not a product surface, and nothing in the ingestion path
 * populates it anyway.
 */
export function IODetailBlocks({ io }: { io: IODetail | null | undefined }) {
  if (!io) return null;

  const { parameters, initial_conditions, data_inputs, outputs } = io;
  const protocol = io.experiment_protocol;

  return (
    <div className="flex flex-col gap-6">
      {parameters && parameters.length > 0 && (
        <div>
          <SubHeading>Parameters</SubHeading>
          <DataTable
            columns={['Name', 'Default', 'Unit', 'Meaning']}
            rows={parameters.map((p) => [
              <span key="n" className="font-mono">
                {p.name}
              </span>,
              formatValue(p.default_value),
              p.unit || <NotRecorded>—</NotRecorded>,
              p.biological_meaning || p.description || (
                <NotRecorded>—</NotRecorded>
              ),
            ])}
          />
        </div>
      )}

      {initial_conditions && initial_conditions.length > 0 && (
        <div>
          <SubHeading>Initial conditions</SubHeading>
          <DataTable
            columns={['Name', 'Value', 'Unit']}
            rows={initial_conditions.map((c) => [
              <span key="n" className="font-mono">
                {c.name}
              </span>,
              formatValue(c.value),
              c.unit || <NotRecorded>—</NotRecorded>,
            ])}
          />
        </div>
      )}

      {data_inputs && data_inputs.length > 0 && (
        <div>
          <SubHeading>Data inputs</SubHeading>
          <DataTable
            columns={['Name', 'Format', 'Required', 'Purpose']}
            rows={data_inputs.map((d) => [
              <span key="n" className="font-mono">
                {d.name}
              </span>,
              d.format || <NotRecorded>—</NotRecorded>,
              d.required ? <Chip tone="secondary">Required</Chip> : 'Optional',
              d.purpose || <NotRecorded>—</NotRecorded>,
            ])}
          />
        </div>
      )}

      {outputs && outputs.length > 0 && (
        <div>
          <SubHeading>Outputs</SubHeading>
          <DataTable
            columns={['Name', 'Quantity', 'Unit', 'Format']}
            rows={outputs.map((o) => [
              <span key="n" className="font-mono">
                {o.name}
              </span>,
              o.quantity_kind || o.description || <NotRecorded>—</NotRecorded>,
              o.unit || <NotRecorded>—</NotRecorded>,
              o.format || <NotRecorded>—</NotRecorded>,
            ])}
          />
        </div>
      )}

      {protocol && <Protocol protocol={protocol} />}
    </div>
  );
}

function Protocol({
  protocol,
}: {
  protocol: NonNullable<IODetail['experiment_protocol']>;
}) {
  const timestep = joinQuantity(protocol.timestep, protocol.timestep_unit);
  const duration = joinQuantity(protocol.duration, protocol.duration_unit);
  const observables = protocol.observables ?? [];

  if (
    !protocol.description &&
    !timestep &&
    !duration &&
    observables.length === 0
  ) {
    return null;
  }

  return (
    <div>
      <SubHeading>Experiment protocol</SubHeading>
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
    </div>
  );
}

/**
 * A compact data table.
 *
 * Wrapped in its own `overflow-x-auto` so a wide table scrolls itself rather
 * than forcing the whole page to scroll sideways — the failure mode long
 * dependency names and file paths already caused elsewhere on this page.
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
    return <NotRecorded>—</NotRecorded>;
  }
  if (typeof value === 'object') {
    return <code className="font-mono text-xs">{JSON.stringify(value)}</code>;
  }
  return <span className="font-mono text-xs">{String(value)}</span>;
}

function joinQuantity(
  value: number | null | undefined,
  unit: string | null | undefined
): string {
  if (typeof value !== 'number') return '';
  return `${value} ${unit || ''}`.trim();
}
