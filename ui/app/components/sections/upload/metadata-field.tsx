import { Input, Textarea, Chip } from '@heroui/react';
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
  /** Full form state — needed so editable ontology list items can read their indexed keys */
  formValues?: FormValues;
};

const FORCE_EDITABLE_TYPES = new Set([
  'text',
  'object-scalar',
  'textarea',
  'boolean',
  'list-scalar',
  'list-ontology',
]);

export function MetadataField({
  fieldKey,
  annotation,
  value,
  confidence,
  onChange,
  items,
  forceEditable,
  formValues,
}: MetadataFieldProps) {
  const isEditable =
    annotation.visibility === 'editable' ||
    (forceEditable === true && FORCE_EDITABLE_TYPES.has(annotation.inputType));

  if (isEditable && annotation.inputType === 'list-ontology') {
    return (
      <EditableOntologyList
        fieldKey={fieldKey}
        annotation={annotation}
        items={items ?? []}
        formValues={formValues ?? {}}
        onChange={onChange}
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
  return <ViewableField annotation={annotation} value={value} items={items} />;
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
  const showConfidence = annotation.hasConfidence === true;

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

  if (!showConfidence) return mainInput;

  return (
    <div className="flex flex-col gap-1.5">
      {mainInput}
      <div className="flex items-center gap-2 pl-1">
        <span className="text-xs text-default-800 shrink-0">Confidence</span>
        <select
          value={confidence ?? ''}
          onChange={(e) => onChange(`${fieldKey}.$confidence`, e.target.value)}
          aria-label={`${annotation.label} confidence`}
          className="text-xs text-default-800 bg-default-200 border border-default-200 rounded px-2 py-1"
        >
          <option value="">—</option>
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
          <option value="none">none</option>
        </select>
      </div>
    </div>
  );
}

// ── Editable ontology list ────────────────────────────────────────────────────

const CONFIDENCE_SELECT_CLASS =
  'text-xs text-default-800 bg-default-200 border border-default-200 rounded px-2 py-1';

function ConfidenceSelect({
  label,
  ariaLabel,
  value,
  onChange,
}: {
  label: string;
  ariaLabel: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-default-800">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={ariaLabel}
        className={CONFIDENCE_SELECT_CLASS}
      >
        <option value="">—</option>
        <option value="high">high</option>
        <option value="medium">medium</option>
        <option value="low">low</option>
        <option value="none">none</option>
      </select>
    </div>
  );
}

function EditableOntologyList({
  fieldKey,
  annotation,
  items,
  formValues,
  onChange,
}: {
  fieldKey: string;
  annotation: FieldAnnotation;
  items: unknown[];
  formValues: FormValues;
  onChange: (key: string, value: string) => void;
}) {
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
          {items.map((item, index) => {
            const record = item as Record<string, unknown>;
            const label = String(
              record['ontology_label'] ?? record['value'] ?? ''
            );
            const iri = record['iri'] ? String(record['iri']) : null;
            const ontology = record['ontology']
              ? String(record['ontology'])
              : null;
            const confKey = `${fieldKey}[${index}].confidence`;
            const mapKey = `${fieldKey}[${index}].mapping_confidence`;
            const conf =
              formValues[confKey] ??
              (record['confidence'] ? String(record['confidence']) : '');
            const mapConf =
              formValues[mapKey] ??
              (record['mapping_confidence']
                ? String(record['mapping_confidence'])
                : '');

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
                    {iri}
                  </span>
                )}
                {ontology && (
                  <span className="text-xs text-default-800">{ontology}</span>
                )}
                <div className="flex items-center gap-4 pt-0.5">
                  <ConfidenceSelect
                    label="Confidence"
                    ariaLabel={`${label} confidence`}
                    value={conf}
                    onChange={(v) => onChange(confKey, v)}
                  />
                  <ConfidenceSelect
                    label="Map confidence"
                    ariaLabel={`${label} mapping confidence`}
                    value={mapConf}
                    onChange={(v) => onChange(mapKey, v)}
                  />
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

// ── Viewable renderer ─────────────────────────────────────────────────────────

type ViewableFieldProps = {
  annotation: FieldAnnotation;
  value: string;
  items?: unknown[];
};

function ViewableField({ annotation, value, items }: ViewableFieldProps) {
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
    annotation.inputType === 'list-object'
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
          {list.map((item, index) => (
            <div
              key={index}
              className="text-xs bg-default-50 border border-default-200 rounded px-3 py-2 font-mono text-default-800"
            >
              {formatObjectItem(item)}
            </div>
          ))}
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
