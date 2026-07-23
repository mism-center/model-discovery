import type { ModelDetailResponse } from '~/api/endpoints/models';
import { SectionCard, Chip } from './primitives';

type IOSpec = NonNullable<ModelDetailResponse['io_spec']>;
type IOSlot = NonNullable<IOSpec['inputs']>[number];

/**
 * Renders the model's input/output handshake: the slots a run consumes and
 * produces, plus the JSON-Schema for its parameters. Returns null when the
 * model declares no I/O spec (e.g. non-executable resources).
 */
export function IOSpecSection({ model }: { model: ModelDetailResponse }) {
  const spec = model.io_spec;
  if (!spec) return null;

  const inputs = spec.inputs ?? [];
  const outputs = spec.outputs ?? [];
  const hasParams =
    spec.parameters_schema && Object.keys(spec.parameters_schema).length > 0;

  if (inputs.length === 0 && outputs.length === 0 && !hasParams) return null;

  return (
    <SectionCard
      title="Inputs & outputs"
      description="The data this model consumes and produces when executed."
    >
      <div className="grid gap-6 sm:grid-cols-2">
        <SlotColumn title="Inputs" slots={inputs} />
        <SlotColumn title="Outputs" slots={outputs} />
      </div>

      {hasParams && (
        <details className="mt-6 group">
          <summary className="cursor-pointer select-none text-[11px] font-bold uppercase tracking-wider text-default-600 hover:text-primary">
            Parameters schema
          </summary>
          <pre className="mt-2 max-h-96 overflow-auto rounded-lg bg-default-100 p-3 text-[12px] font-mono text-default-900">
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
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-default-600 mb-3">
        {title}
      </h3>
      {slots.length === 0 ? (
        <p className="text-sm text-default-500">None declared.</p>
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
                <p className="mt-1 text-[13px] text-default-700">
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
