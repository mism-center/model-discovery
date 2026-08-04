import type { ModelDetailResponse } from '~/api/endpoints/models';
import { IODetailBlocks } from './io-detail';
import { NotRecorded, SectionCard, SubHeading, Chip } from './primitives';

type IOSpec = NonNullable<ModelDetailResponse['io_spec']>;
type IOSlot = NonNullable<IOSpec['inputs']>[number];

/**
 * The model's inputs and outputs.
 *
 * Two sources, in priority order:
 *   1. `model.io` — the rich Section C characterization (parameters with units
 *      and biological meaning, initial conditions, data inputs, outputs,
 *      experiment protocol). This is what a researcher actually needs.
 *   2. `model.io_spec` — the machine handshake (slot names + tags + JSON
 *      Schema) used to validate a run. Shown only as a secondary detail.
 *
 * Renders even when both are empty, which in practice is most models: nothing in
 * the ingestion path writes either, and a missing I/O contract is precisely what
 * someone deciding whether they can run this model needs to be told. The first
 * pass returned `null` here, so the question went unanswered.
 */
export function IOSpecSection({ model }: { model: ModelDetailResponse }) {
  const spec = model.io_spec;
  const inputs = spec?.inputs ?? [];
  const outputs = spec?.outputs ?? [];
  const hasParams = Boolean(
    spec?.parameters_schema && Object.keys(spec.parameters_schema).length > 0
  );
  const io = model.io;
  const hasIODetail = Boolean(
    io &&
    ((io.parameters?.length ?? 0) > 0 ||
      (io.initial_conditions?.length ?? 0) > 0 ||
      (io.data_inputs?.length ?? 0) > 0 ||
      (io.outputs?.length ?? 0) > 0 ||
      io.experiment_protocol)
  );
  const hasSlots = inputs.length > 0 || outputs.length > 0;

  return (
    <SectionCard
      title="Inputs & outputs"
      description="The data this model consumes and produces when executed."
    >
      {hasIODetail && <IODetailBlocks io={io} />}

      {!hasIODetail && !hasSlots && !hasParams && (
        <p className="text-sm">
          <NotRecorded>
            This model has not been characterized, so its inputs and outputs are
            unknown.
          </NotRecorded>
        </p>
      )}

      {hasSlots && (
        <div className={hasIODetail ? 'mt-6' : undefined}>
          {hasIODetail && <SubHeading>Run handshake</SubHeading>}
          <div className="grid gap-6 sm:grid-cols-2">
            <SlotColumn title="Inputs" slots={inputs} />
            <SlotColumn title="Outputs" slots={outputs} />
          </div>
        </div>
      )}

      {hasParams && spec?.parameters_schema && (
        <details className="mt-6">
          <summary className="cursor-pointer select-none text-sm font-semibold text-default-900 hover:text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded">
            Parameters schema
          </summary>
          {/*
           * tabIndex makes the scroll region reachable by keyboard — a
           * scrollable box that can only be scrolled with a pointer is a trap
           * for anyone navigating without one.
           */}
          <pre
            tabIndex={0}
            className="mt-2 max-h-96 overflow-auto rounded-lg bg-default-100 p-3 text-xs font-mono text-default-900"
          >
            {JSON.stringify(spec.parameters_schema, null, 2)}
          </pre>
        </details>
      )}
    </SectionCard>
  );
}

function SlotColumn({ title, slots }: { title: string; slots: IOSlot[] }) {
  return (
    <div>
      <h3 className="text-xs font-bold uppercase tracking-wider text-default-800 mb-3">
        {title}
      </h3>
      {slots.length === 0 ? (
        <p className="text-sm text-default-800">None declared.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {slots.map((slot) => (
            <li
              key={slot.name}
              className="rounded-lg border border-default-200 p-3"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-default-900">
                  {slot.name}
                </span>
                {slot.required && <Chip tone="secondary">Required</Chip>}
              </div>
              {slot.description && (
                <p className="mt-1 text-sm text-default-900">
                  {slot.description}
                </p>
              )}
              {slot.tags && slot.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {slot.tags.map((t) => (
                    <Chip key={t} tone="neutral">
                      {t}
                    </Chip>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
