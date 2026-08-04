import { Button, Input, Textarea, Chip } from '@heroui/react';
import type { FieldAnnotation, FormValues } from './metadata-types';

type MetadataFieldProps = {
  fieldKey: string;
  annotation: FieldAnnotation;
  value: string;
  confidence?: string;
  onChange: (key: string, newValue: string) => void;
  /** Raw list items for list-object / list-ontology fields */
  items?: unknown[];
  /** When true, viewable fields that support editing are rendered as inputs */
  forceEditable?: boolean;
  /** Read current form value by key — used by editable list components for per-item editing */
  getFormValue?: (key: string) => string;
  /** Full form values map — used to count items added via the UI beyond the original YAML */
  formValues?: FormValues;
};

const FORCE_EDITABLE_TYPES = new Set([
  'text',
  'object-scalar',
  'textarea',
  'boolean',
  'list-scalar',
  'list-ontology',
  'list-entry-point',
  'list-container',
  'list-dep',
]);

export function MetadataField({
  fieldKey,
  annotation,
  value,
  confidence,
  onChange,
  items,
  forceEditable,
  getFormValue,
  formValues,
}: MetadataFieldProps) {
  const isEditable =
    annotation.visibility === 'editable' ||
    (forceEditable === true &&
      annotation.forceReadOnly !== true &&
      FORCE_EDITABLE_TYPES.has(annotation.inputType));

  // ── Helpers for add-item lists ──────────────────────────────────────────────
  // Count how many items exist in formValues for this field by probing indexed keys.
  const countItems = (primarySubfield: string): number => {
    if (!formValues) return items?.length ?? 0;
    let i = 0;
    while (`${fieldKey}[${i}].${primarySubfield}` in formValues) i++;
    return i;
  };

  // Returns a handler that appends one empty item to the list in form state.
  const makeAddItemHandler = (subfields: string[]) => () => {
    const i = countItems(subfields[0]);
    for (const sf of subfields) onChange(`${fieldKey}[${i}].${sf}`, '');
  };

  if (isEditable && annotation.inputType === 'list-ontology') {
    return (
      <EditableOntologyList
        annotation={annotation}
        items={items ?? []}
        fieldKey={fieldKey}
        onChange={onChange}
        getFormValue={getFormValue}
      />
    );
  }

  if (isEditable && annotation.inputType === 'list-entry-point') {
    const itemCount = countItems('command');
    return (
      <EditableEntryPointList
        annotation={annotation}
        itemCount={itemCount}
        fieldKey={fieldKey}
        onChange={onChange}
        getFormValue={getFormValue}
        formValues={formValues}
        onAddItem={makeAddItemHandler([
          'command',
          'purpose',
          'default_output_location',
          'confidence',
          'source',
        ])}
      />
    );
  }

  if (isEditable && annotation.inputType === 'list-container') {
    const itemCount = countItems('kind');
    return (
      <EditableContainerList
        annotation={annotation}
        itemCount={itemCount}
        fieldKey={fieldKey}
        onChange={onChange}
        getFormValue={getFormValue}
        onAddItem={makeAddItemHandler(['kind', 'file', 'image_name', 'source'])}
      />
    );
  }

  if (isEditable && annotation.inputType === 'list-dep') {
    const itemCount = countItems('name');
    return (
      <EditableDependencyList
        annotation={annotation}
        itemCount={itemCount}
        fieldKey={fieldKey}
        onChange={onChange}
        getFormValue={getFormValue}
        onAddItem={makeAddItemHandler(['name', 'version_constraint', 'source'])}
      />
    );
  }

  if (isEditable) {
    return (
      <EditableField
        fieldKey={fieldKey}
        annotation={annotation}
        value={value}
        confidence={confidence}
        onChange={onChange}
      />
    );
  }
  return (
    <ViewableField
      annotation={annotation}
      value={value}
      items={items}
      confidence={confidence}
    />
  );
}

// ── Editable renderer ─────────────────────────────────────────────────────────

type EditableFieldProps = {
  fieldKey: string;
  annotation: FieldAnnotation;
  value: string;
  confidence?: string;
  onChange: (key: string, newValue: string) => void;
};

function EditableField({
  fieldKey,
  annotation,
  value,
  confidence,
  onChange,
}: EditableFieldProps) {
  const label = annotation.required
    ? `${annotation.label} *`
    : annotation.label;

  if (annotation.inputType === 'boolean') {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-xs text-default-800 font-medium">{label}</span>
        <select
          value={value}
          onChange={(e) => onChange(fieldKey, e.target.value)}
          className="text-xs text-default-800 bg-default-200 border border-default-200 rounded px-2 py-1 max-w-[100px]"
        >
          <option value="">—</option>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
        {annotation.description && (
          <span className="text-xs text-default-800">
            {annotation.description}
          </span>
        )}
      </div>
    );
  }

  const mainInput =
    annotation.inputType === 'textarea' ? (
      <Textarea
        label={label}
        description={annotation.description}
        placeholder={annotation.placeholder}
        value={value}
        minRows={3}
        onValueChange={(v) => onChange(fieldKey, v)}
        classNames={{ label: 'text-xs text-default-800 font-medium' }}
      />
    ) : (
      <Input
        label={label}
        description={annotation.description}
        placeholder={annotation.placeholder}
        value={value}
        onValueChange={(v) => onChange(fieldKey, v)}
        classNames={{ label: 'text-xs text-default-800 font-medium' }}
      />
    );

  return (
    <div className="flex flex-col gap-1.5">
      {mainInput}
      {confidence && (
        <div className="flex items-center gap-2 pl-1">
          <span className="text-xs text-default-800 shrink-0">Confidence</span>
          <ConfidenceBadge value={confidence} />
        </div>
      )}
    </div>
  );
}

// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfidenceBadge({ value }: { value: string }) {
  const colorMap: Record<string, 'danger' | 'warning' | 'success' | 'default'> =
    { none: 'danger', inferred: 'danger', medium: 'warning', high: 'success' };
  const color = colorMap[value] ?? 'default';
  return (
    <Chip size="sm" color={color} variant="flat">
      {value}
    </Chip>
  );
}

// ── Editable ontology list ────────────────────────────────────────────────────

function EditableOntologyList({
  annotation,
  items,
  fieldKey,
  onChange,
  getFormValue,
}: {
  annotation: FieldAnnotation;
  items: unknown[];
  fieldKey: string;
  onChange: (key: string, newValue: string) => void;
  getFormValue?: (key: string) => string;
}) {
  const gv = (key: string) => getFormValue?.(key) ?? '';

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
        {items.length > 0 && (
          <span className="ml-1.5 text-default-800">({items.length})</span>
        )}
      </span>
      {items.length === 0 ? (
        <span className="text-xs text-default-800 italic">none</span>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((_, index) => {
            const conf = gv(`${fieldKey}[${index}].confidence`);
            const mapConf = gv(`${fieldKey}[${index}].mapping_confidence`);

            return (
              <div
                key={index}
                className="bg-white border border-default-200 rounded px-3 py-2 flex flex-col gap-2"
              >
                <Input
                  label="label"
                  value={gv(`${fieldKey}[${index}].ontology_label`)}
                  onValueChange={(v) =>
                    onChange(`${fieldKey}[${index}].ontology_label`, v)
                  }
                  classNames={{ label: 'text-xs text-default-800 font-medium' }}
                />
                <Input
                  label="iri"
                  value={gv(`${fieldKey}[${index}].iri`)}
                  onValueChange={(v) =>
                    onChange(`${fieldKey}[${index}].iri`, v)
                  }
                  classNames={{
                    label: 'text-xs text-default-800 font-medium',
                    input: 'font-mono',
                  }}
                />
                <Input
                  label="ontology"
                  value={gv(`${fieldKey}[${index}].ontology`)}
                  onValueChange={(v) =>
                    onChange(`${fieldKey}[${index}].ontology`, v)
                  }
                  classNames={{ label: 'text-xs text-default-800 font-medium' }}
                />
                <Input
                  label="source"
                  value={gv(`${fieldKey}[${index}].source`)}
                  onValueChange={(v) =>
                    onChange(`${fieldKey}[${index}].source`, v)
                  }
                  classNames={{ label: 'text-xs text-default-800 font-medium' }}
                />
                <div className="flex items-center gap-4 pt-0.5">
                  {conf && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-default-800">
                        Confidence
                      </span>
                      <ConfidenceBadge value={conf} />
                    </div>
                  )}
                  {mapConf && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-default-800">
                        Map confidence
                      </span>
                      <ConfidenceBadge value={mapConf} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

// ── Editable entry-point list ─────────────────────────────────────────────────

function EditableEntryPointList({
  annotation,
  itemCount,
  fieldKey,
  onChange,
  getFormValue,
  onAddItem,
  formValues,
}: {
  annotation: FieldAnnotation;
  itemCount: number;
  fieldKey: string;
  onChange: (key: string, newValue: string) => void;
  getFormValue?: (key: string) => string;
  onAddItem: () => void;
  formValues?: FormValues;
}) {
  const gv = (key: string) => getFormValue?.(key) ?? '';

  const countArgs = (epIndex: number): number => {
    if (!formValues) return 0;
    let j = 0;
    while (`${fieldKey}[${epIndex}].arguments[${j}].name` in formValues) j++;
    return j;
  };

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
        {itemCount > 0 && (
          <span className="ml-1.5 text-default-800">({itemCount})</span>
        )}
      </span>
      <div className="flex flex-col gap-3">
        {Array.from({ length: itemCount }, (_, index) => {
          const conf = gv(`${fieldKey}[${index}].confidence`);
          const source = gv(`${fieldKey}[${index}].source`);
          const argCount = countArgs(index);
          return (
            <div
              key={index}
              className="bg-white border border-default-200 rounded px-3 py-2 flex flex-col gap-2"
            >
              <Input
                label="command"
                value={gv(`${fieldKey}[${index}].command`)}
                onValueChange={(v) =>
                  onChange(`${fieldKey}[${index}].command`, v)
                }
                classNames={{
                  label: 'text-xs text-default-800 font-medium',
                  input: 'font-mono',
                }}
              />
              <Textarea
                label="purpose"
                value={gv(`${fieldKey}[${index}].purpose`)}
                minRows={2}
                onValueChange={(v) =>
                  onChange(`${fieldKey}[${index}].purpose`, v)
                }
                classNames={{ label: 'text-xs text-default-800 font-medium' }}
              />
              <Input
                label="default output location"
                value={gv(`${fieldKey}[${index}].default_output_location`)}
                onValueChange={(v) =>
                  onChange(`${fieldKey}[${index}].default_output_location`, v)
                }
                classNames={{
                  label: 'text-xs text-default-800 font-medium',
                  input: 'font-mono',
                }}
              />

              {/* ── Arguments sub-section ── */}
              <div className="flex flex-col gap-1.5 mt-1">
                <span className="text-xs text-default-600 font-semibold uppercase tracking-wide">
                  Arguments ({argCount})
                </span>
                {argCount > 0 && (
                  <div className="flex flex-col gap-2">
                    {Array.from({ length: argCount }, (_, j) => (
                      <div
                        key={j}
                        className="bg-default-50 border border-default-200 rounded px-3 py-2 flex flex-col gap-2"
                      >
                        <Input
                          label="name"
                          value={gv(
                            `${fieldKey}[${index}].arguments[${j}].name`
                          )}
                          onValueChange={(v) =>
                            onChange(
                              `${fieldKey}[${index}].arguments[${j}].name`,
                              v
                            )
                          }
                          classNames={{
                            label: 'text-xs text-default-800 font-medium',
                            input: 'font-mono',
                          }}
                        />
                        <Textarea
                          label="description"
                          value={gv(
                            `${fieldKey}[${index}].arguments[${j}].description`
                          )}
                          minRows={2}
                          onValueChange={(v) =>
                            onChange(
                              `${fieldKey}[${index}].arguments[${j}].description`,
                              v
                            )
                          }
                          classNames={{
                            label: 'text-xs text-default-800 font-medium',
                          }}
                        />
                        <Input
                          label="default"
                          value={gv(
                            `${fieldKey}[${index}].arguments[${j}].default`
                          )}
                          onValueChange={(v) =>
                            onChange(
                              `${fieldKey}[${index}].arguments[${j}].default`,
                              v
                            )
                          }
                          classNames={{
                            label: 'text-xs text-default-800 font-medium',
                            input: 'font-mono',
                          }}
                        />
                        <Input
                          label="data type"
                          value={gv(
                            `${fieldKey}[${index}].arguments[${j}].data_type`
                          )}
                          onValueChange={(v) =>
                            onChange(
                              `${fieldKey}[${index}].arguments[${j}].data_type`,
                              v
                            )
                          }
                          classNames={{
                            label: 'text-xs text-default-800 font-medium',
                          }}
                          description="bool | int | float | str"
                        />
                        <Input
                          label="position"
                          value={gv(
                            `${fieldKey}[${index}].arguments[${j}].position`
                          )}
                          onValueChange={(v) =>
                            onChange(
                              `${fieldKey}[${index}].arguments[${j}].position`,
                              v
                            )
                          }
                          classNames={{
                            label: 'text-xs text-default-800 font-medium',
                            input: 'font-mono',
                          }}
                          description="Argument order (0-based)"
                        />
                        <div className="flex flex-col gap-1">
                          <span className="text-xs text-default-800 font-medium">
                            user can override
                          </span>
                          <select
                            value={gv(
                              `${fieldKey}[${index}].arguments[${j}].user_can_override`
                            )}
                            onChange={(e) =>
                              onChange(
                                `${fieldKey}[${index}].arguments[${j}].user_can_override`,
                                e.target.value
                              )
                            }
                            className="text-xs text-default-800 bg-default-200 border border-default-200 rounded px-2 py-1 max-w-[100px]"
                          >
                            <option value="">—</option>
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <Button
                  size="sm"
                  color="default"
                  variant="flat"
                  className="self-start text-xs"
                  onPress={() => {
                    const j = argCount;
                    onChange(`${fieldKey}[${index}].arguments[${j}].name`, '');
                    onChange(
                      `${fieldKey}[${index}].arguments[${j}].description`,
                      ''
                    );
                    onChange(
                      `${fieldKey}[${index}].arguments[${j}].default`,
                      ''
                    );
                    onChange(
                      `${fieldKey}[${index}].arguments[${j}].data_type`,
                      ''
                    );
                    onChange(
                      `${fieldKey}[${index}].arguments[${j}].user_can_override`,
                      ''
                    );
                    onChange(
                      `${fieldKey}[${index}].arguments[${j}].position`,
                      ''
                    );
                  }}
                >
                  + Add Argument
                </Button>
              </div>

              {/* ── Confidence / source footer ── */}
              <div className="flex items-center gap-4 pt-0.5 flex-wrap">
                {conf && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-default-800">Confidence</span>
                    <ConfidenceBadge value={conf} />
                  </div>
                )}
                {source && (
                  <span className="text-xs text-default-500 font-mono truncate">
                    source: {source}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <Button
        size="sm"
        color="success"
        variant="flat"
        className="self-start mt-1 text-xs"
        onPress={onAddItem}
      >
        + Add Entry Point
      </Button>
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

// ── Editable container list ───────────────────────────────────────────────────

function EditableContainerList({
  annotation,
  itemCount,
  fieldKey,
  onChange,
  getFormValue,
  onAddItem,
}: {
  annotation: FieldAnnotation;
  itemCount: number;
  fieldKey: string;
  onChange: (key: string, newValue: string) => void;
  getFormValue?: (key: string) => string;
  onAddItem: () => void;
}) {
  const gv = (key: string) => getFormValue?.(key) ?? '';

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
        {itemCount > 0 && (
          <span className="ml-1.5 text-default-800">({itemCount})</span>
        )}
      </span>
      <div className="flex flex-col gap-3">
        {Array.from({ length: itemCount }, (_, index) => (
          <div
            key={index}
            className="bg-white border border-default-200 rounded px-3 py-2 flex flex-col gap-2"
          >
            <Input
              label="kind"
              value={gv(`${fieldKey}[${index}].kind`)}
              onValueChange={(v) => onChange(`${fieldKey}[${index}].kind`, v)}
              classNames={{ label: 'text-xs text-default-800 font-medium' }}
              description="docker | singularity"
            />
            <Input
              label="file"
              value={gv(`${fieldKey}[${index}].file`)}
              onValueChange={(v) => onChange(`${fieldKey}[${index}].file`, v)}
              classNames={{
                label: 'text-xs text-default-800 font-medium',
                input: 'font-mono',
              }}
              description="e.g. Dockerfile, container.def"
            />
            <Input
              label="image name"
              value={gv(`${fieldKey}[${index}].image_name`)}
              onValueChange={(v) =>
                onChange(`${fieldKey}[${index}].image_name`, v)
              }
              classNames={{
                label: 'text-xs text-default-800 font-medium',
                input: 'font-mono',
              }}
            />
            <Input
              label="source"
              value={gv(`${fieldKey}[${index}].source`)}
              onValueChange={(v) => onChange(`${fieldKey}[${index}].source`, v)}
              classNames={{
                label: 'text-xs text-default-800 font-medium',
                input: 'font-mono',
              }}
            />
          </div>
        ))}
      </div>
      <Button
        size="sm"
        color="success"
        variant="flat"
        className="self-start mt-1 text-xs"
        onPress={onAddItem}
      >
        + Add Container
      </Button>
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

// ── Editable dependency list ──────────────────────────────────────────────────

function EditableDependencyList({
  annotation,
  itemCount,
  fieldKey,
  onChange,
  getFormValue,
  onAddItem,
}: {
  annotation: FieldAnnotation;
  itemCount: number;
  fieldKey: string;
  onChange: (key: string, newValue: string) => void;
  getFormValue?: (key: string) => string;
  onAddItem: () => void;
}) {
  const gv = (key: string) => getFormValue?.(key) ?? '';

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
        {itemCount > 0 && (
          <span className="ml-1.5 text-default-800">({itemCount})</span>
        )}
      </span>
      <div className="flex flex-col gap-3">
        {Array.from({ length: itemCount }, (_, index) => (
          <div
            key={index}
            className="bg-white border border-default-200 rounded px-3 py-2 flex flex-col gap-2"
          >
            <Input
              label="name"
              value={gv(`${fieldKey}[${index}].name`)}
              onValueChange={(v) => onChange(`${fieldKey}[${index}].name`, v)}
              classNames={{
                label: 'text-xs text-default-800 font-medium',
                input: 'font-mono',
              }}
            />
            <Input
              label="version constraint"
              value={gv(`${fieldKey}[${index}].version_constraint`)}
              onValueChange={(v) =>
                onChange(`${fieldKey}[${index}].version_constraint`, v)
              }
              classNames={{
                label: 'text-xs text-default-800 font-medium',
                input: 'font-mono',
              }}
              description="e.g. >=1.2,<2.0"
            />
            <Input
              label="source"
              value={gv(`${fieldKey}[${index}].source`)}
              onValueChange={(v) => onChange(`${fieldKey}[${index}].source`, v)}
              classNames={{
                label: 'text-xs text-default-800 font-medium',
                input: 'font-mono',
              }}
            />
          </div>
        ))}
      </div>
      <Button
        size="sm"
        color="success"
        variant="flat"
        className="self-start mt-1 text-xs"
        onPress={onAddItem}
      >
        + Add Dependency
      </Button>
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

// ── Viewable renderer ─────────────────────────────────────────────────────────

type ViewableFieldProps = {
  annotation: FieldAnnotation;
  value: string;
  items?: unknown[];
  confidence?: string;
};

function ViewableField({
  annotation,
  value,
  items,
  confidence,
}: ViewableFieldProps) {
  if (annotation.inputType === 'preformatted') {
    const isEmpty = !value || value === 'null' || value === '';
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-xs text-default-800 font-medium">
          {annotation.label}
        </span>
        {isEmpty ? (
          <span className="text-xs text-default-500 italic">not set</span>
        ) : (
          <pre className="text-xs text-default-800 font-mono bg-default-50 border border-default-200 rounded p-2 overflow-auto whitespace-pre-wrap break-all">
            {value}
          </pre>
        )}
      </div>
    );
  }

  if (
    annotation.inputType === 'list-ontology' ||
    annotation.inputType === 'list-object' ||
    annotation.inputType === 'list-entry-point' ||
    annotation.inputType === 'list-container' ||
    annotation.inputType === 'list-dep'
  ) {
    return <ObjectListField annotation={annotation} items={items} />;
  }

  if (annotation.inputType === 'list-scalar') {
    return <ChipListField annotation={annotation} value={value} />;
  }

  if (annotation.inputType === 'boolean') {
    return <BooleanField annotation={annotation} value={value} />;
  }

  // text / object-scalar / static
  const isEmpty =
    !value || value === 'null' || value === 'undefined' || value === '';
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
      </span>
      <span className="text-sm text-default-800">
        {isEmpty ? (
          <span className="text-default-500 italic">not set</span>
        ) : (
          value
        )}
      </span>
      {confidence && (
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className="text-xs text-default-800 shrink-0">Confidence</span>
          <ConfidenceBadge value={confidence} />
        </div>
      )}
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

// ── Sub-renderers ─────────────────────────────────────────────────────────────

function ChipListField({
  annotation,
  value,
}: {
  annotation: FieldAnnotation;
  value: string;
}) {
  const parts = value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
      </span>
      {parts.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {parts.map((part) => (
            <Chip key={part} size="sm" variant="flat" color="default">
              {part}
            </Chip>
          ))}
        </div>
      ) : (
        <span className="text-xs text-default-800 italic">none</span>
      )}
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

function BooleanField({
  annotation,
  value,
}: {
  annotation: FieldAnnotation;
  value: string;
}) {
  const colorMap: Record<string, 'success' | 'default' | 'warning'> = {
    true: 'success',
    false: 'default',
  };
  const color: 'success' | 'default' | 'warning' = colorMap[value] ?? 'warning';

  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
      </span>
      <Chip size="sm" color={color} variant="flat">
        {value || 'unknown'}
      </Chip>
      {annotation.description && (
        <span className="text-xs text-default-800">
          {annotation.description}
        </span>
      )}
    </div>
  );
}

function ObjectListField({
  annotation,
  items,
}: {
  annotation: FieldAnnotation;
  items?: unknown[];
}) {
  const list = Array.isArray(items) ? items : [];
  const isOntology = annotation.inputType === 'list-ontology';

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs text-default-800 font-medium">
        {annotation.label}
        {list.length > 0 && (
          <span className="ml-1.5 text-default-800">({list.length})</span>
        )}
      </span>
      {list.length === 0 ? (
        <span className="text-xs text-default-800 italic">none</span>
      ) : (
        <div className="flex flex-col gap-1.5">
          {list.map((item, index) => {
            if (isOntology) {
              const record = item as Record<string, unknown>;
              const label = String(
                record['ontology_label'] ?? record['value'] ?? ''
              );
              const iri = record['iri'] ? String(record['iri']) : null;
              const ontology = record['ontology']
                ? String(record['ontology'])
                : null;
              const source = record['source'] ? String(record['source']) : null;
              const conf = record['confidence']
                ? String(record['confidence'])
                : '';
              const mapConf = record['mapping_confidence']
                ? String(record['mapping_confidence'])
                : '';
              return (
                <div
                  key={index}
                  className="bg-default-100 border border-default-200 rounded px-3 py-2 flex flex-col gap-1.5"
                >
                  <span className="text-xs font-medium text-default-800">
                    {label}
                  </span>
                  {iri && (
                    <span className="text-xs text-default-800 font-mono break-all">
                      iri: {iri}
                    </span>
                  )}
                  {ontology && (
                    <span className="text-xs text-default-800">
                      ontology: {ontology}
                    </span>
                  )}
                  {source && (
                    <span className="text-xs text-default-800">
                      source: {source}
                    </span>
                  )}
                  <div className="flex items-center gap-4 pt-0.5">
                    {conf && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-default-800">
                          Confidence
                        </span>
                        <ConfidenceBadge value={conf} />
                      </div>
                    )}
                    {mapConf && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-default-800">
                          Map confidence
                        </span>
                        <ConfidenceBadge value={mapConf} />
                      </div>
                    )}
                  </div>
                </div>
              );
            }
            // list-object: authors, contacts, publications, funding, etc.
            return (
              <div
                key={index}
                className="text-xs bg-default-50 border border-default-200 rounded px-3 py-2 font-mono text-default-800"
              >
                {formatObjectItem(item)}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatObjectItem(item: unknown): string {
  if (typeof item !== 'object' || item === null) return String(item);
  const record = item as Record<string, unknown>;
  const priority = [
    'ontology_label',
    'name',
    // entry_points fields
    'command',
    'purpose',
    'default_output_location',
    // dependency fields
    'version_constraint',
    // container fields
    'kind',
    'file',
    'image_name',
    // generic / shared
    'field_path',
    'path',
    'value',
    'title',
    'doi',
    'url',
    'email',
    'spdx_id',
    'iri',
    'ontology',
    'confidence',
    'mapping_confidence',
    'reason',
  ];
  const parts: string[] = [];
  for (const key of priority) {
    const v = record[key];
    if (v !== undefined && v !== null && v !== '') {
      parts.push(`${key}: ${String(v)}`);
    }
  }
  return parts.length > 0 ? parts.join(' · ') : JSON.stringify(item);
}
