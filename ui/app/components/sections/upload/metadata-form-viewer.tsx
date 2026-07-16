import { useMemo, useState } from 'react';
import { parse as yamlParse, stringify as yamlStringify } from 'yaml';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Tab,
  Tabs,
} from '@heroui/react';

import type { FormValues, ParsedMetadataYaml } from './metadata-types';
import { ANNOTATION_TEMPLATE } from './metadata-template';
import {
  applyFormValuesToMetadata,
  extractFormValues,
} from './metadata-extractor';
import { MetadataField } from './metadata-field';

// ── Types ─────────────────────────────────────────────────────────────────────

type RawFile = { filename: string; content: string };

type AnnotationFile = { path: string; name: string; url: string };

type MetadataFormViewerProps = {
  modelId: string;
  rawFiles: RawFile[];
  onSaved: () => void;
  onSaveError: (message: string) => void;
  annotationFiles?: AnnotationFile[];
};

// inputTypes that become editable when forceEditable=true (mirrors FORCE_EDITABLE_TYPES
// in metadata-field.tsx — keep in sync if either list changes)
const VIEWABLE_FORCE_EDITABLE_TYPES = new Set([
  'text',
  'object-scalar',
  'textarea',
  'boolean',
  'list-scalar',
  'list-ontology',
]);

// ── Component ─────────────────────────────────────────────────────────────────

export function MetadataFormViewer({
  modelId,
  rawFiles,
  onSaved,
  onSaveError,
  annotationFiles,
}: MetadataFormViewerProps) {
  const { parsedMeta, metaContent } = useMemo(() => {
    const metaFile = rawFiles.find((f) => f.filename === 'metadata.yaml');
    const metaRaw = metaFile?.content ?? '';

    let meta: ParsedMetadataYaml = {};
    try {
      meta = (yamlParse(metaRaw) as ParsedMetadataYaml | null) ?? {};
    } catch {
      // keep empty — raw tab will still show original
    }

    return { parsedMeta: meta, metaContent: metaRaw };
  }, [rawFiles]);

  const [formValues, setFormValues] = useState<FormValues>(() =>
    extractFormValues(parsedMeta)
  );
  const [sectionEditing, setSectionEditing] = useState<Record<string, boolean>>(
    {}
  );
  const [isDirty, setIsDirty] = useState(false);
  const [saveState, setSaveState] = useState<
    'idle' | 'saving' | 'saved' | 'error'
  >('idle');

  function handleFieldChange(key: string, value: string) {
    setFormValues((prev) => ({ ...prev, [key]: value }));
    setIsDirty(true);
    setSaveState('idle');
  }

  async function handleApprove() {
    setSaveState('saving');

    const updatedMeta = applyFormValuesToMetadata(parsedMeta, formValues);
    const newMetaContent = metaContent
      ? yamlStringify(updatedMeta, { lineWidth: 120 })
      : metaContent;

    try {
      const res = await fetch(
        `/api/v1/models/${encodeURIComponent(modelId)}/metadata-package/raw`,
        {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            files: [{ filename: 'metadata.yaml', content: newMetaContent }],
          }),
        }
      );
      if (!res.ok) {
        const detail = await res.text();
        setSaveState('error');
        onSaveError(detail || `Save failed (${res.status.toString()})`);
        return;
      }
      setSaveState('saved');
      setIsDirty(false);
      onSaved();
    } catch (error: unknown) {
      setSaveState('error');
      onSaveError(error instanceof Error ? error.message : 'Network error');
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Tabs
        aria-label="Metadata sections"
        size="sm"
        variant="underlined"
        classNames={{
          tab: 'data-[hover-unselected=true]:!opacity-100',
          tabContent: 'text-default-800 group-data-[selected=true]:text-foreground group-data-[hover-unselected=true]:font-bold',
          panel: 'pt-0',
        }}
      >
        <Tab key="metadata" title="Metadata">
          <div className="flex flex-col gap-4">
            {(
              [
                {
                  title: 'Identity',
                  noEdit: true,
                  fieldKeys: [
                    'model.name',
                    'model.short_description',
                    'model.long_description',
                    'model.version',
                    'model.external_identifier',
                    'model.license',
                  ],
                },
                {
                  title: 'Model Characteristics',
                  fieldKeys: [
                    'model.multiscale',
                    'model.model_class',
                    'model.formalism',
                    'model.determinism',
                    'model.time_dynamics',
                    'model.spatial',
                    'model.model_scales',
                  ],
                },
                {
                  title: 'Biology',
                  fieldKeys: [
                    'model.biology.species',
                    'model.biology.infectious_agent',
                    'model.biology.health_condition',
                    'model.biology.biological_processes',
                    'model.biology.molecular_entities',
                    'model.biology.proteins_genes',
                    'model.biology.topic_category',
                  ],
                },
                {
                  title: 'People',
                  fieldKeys: [
                    'model.authors',
                    'model.contacts',
                    'model.publications',
                  ],
                },
                {
                  title: 'Resources',
                  fieldKeys: ['model.related_resources', 'model.funding'],
                },
                {
                  title: 'Provenance',
                  fieldKeys: [
                    'provenance.annotated_at',
                    'provenance.annotated_by',
                    'provenance.human_review_required',
                    'provenance.notes',
                    'schema_version',
                    'provenance.source_root',
                    'provenance.files_inspected',
                    'provenance.ontology_lookups',
                    'provenance.unmapped_fields',
                    'provenance.partial_annotation_scope',
                  ],
                },
              ] as const
            ).map(({ title, fieldKeys, ...rest }) => (
              <FieldSection
                key={title}
                title={title}
                fieldKeys={[...fieldKeys]}
                formValues={formValues}
                parsedMeta={parsedMeta}
                onChange={handleFieldChange}
                isEditing={sectionEditing[title] ?? false}
                onEditToggle={(v) =>
                  setSectionEditing((prev) => ({ ...prev, [title]: v }))
                }
                noEdit={'noEdit' in rest && rest.noEdit === true}
              />
            ))}
          </div>
        </Tab>

        <Tab key="annotation" title="Annotation Outputs">
          <div className="flex flex-col gap-3">
            {!annotationFiles || annotationFiles.length === 0 ? (
              <span className="text-xs text-default-500 italic">
                No annotation files
              </span>
            ) : (
              <ul className="flex flex-col gap-2">
                {annotationFiles.map((file) => (
                  <li
                    key={file.path}
                    className="flex items-center justify-between gap-4"
                  >
                    <span className="text-xs font-mono text-default-800 truncate">
                      {file.path}
                    </span>
                    <Button
                      as="a"
                      size="sm"
                      variant="flat"
                      className="text-foreground"
                      href={file.url}
                      download={file.name}
                    >
                      Download
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Tab>

        <Tab key="raw" title="Raw Metadata YAML">
          <div className="flex flex-col gap-3">
            {metaContent ? (
              <pre className="text-xs text-default-800 bg-default-100 rounded p-3 overflow-auto max-h-96 font-mono border border-default-200">
                {metaContent}
              </pre>
            ) : (
              <span className="text-xs text-default-400 italic">
                No metadata available
              </span>
            )}
          </div>
        </Tab>
      </Tabs>

      {/* Approve action bar */}
      <div className="flex items-center gap-2 pt-2 border-t border-default-200">
        <Button
          size="sm"
          color="success"
          variant="flat"
          className="text-foreground"
          isLoading={saveState === 'saving'}
          isDisabled={saveState === 'saving'}
          onPress={() => void handleApprove()}
        >
          Approve
        </Button>
        {isDirty && saveState === 'idle' && (
          <span className="text-xs text-default-800">Unsaved changes</span>
        )}
        {saveState === 'saved' && (
          <span className="text-xs text-success-800">Saved</span>
        )}
      </div>
    </div>
  );
}

// ── FieldSection ──────────────────────────────────────────────────────────────

type FieldSectionProps = {
  title: string;
  fieldKeys: string[];
  formValues: FormValues;
  parsedMeta: ParsedMetadataYaml;
  onChange: (key: string, value: string) => void;
  isEditing: boolean;
  onEditToggle: (v: boolean) => void;
  noEdit?: boolean;
};

function FieldSection({
  title,
  fieldKeys,
  formValues,
  parsedMeta,
  onChange,
  isEditing,
  onEditToggle,
  noEdit = false,
}: FieldSectionProps) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const visibleKeys = fieldKeys.filter((key) => {
    const ann = ANNOTATION_TEMPLATE[key];
    return ann !== undefined && !ann.hidden;
  });

  if (visibleKeys.length === 0) return null;

  // Only show the Edit checkbox when at least one field would actually change
  // rendering when forceEditable is toggled (viewable fields with editable inputTypes).
  const canEdit = visibleKeys.some((key) => {
    const ann = ANNOTATION_TEMPLATE[key];
    return (
      ann?.visibility === 'viewable' &&
      VIEWABLE_FORCE_EDITABLE_TYPES.has(ann.inputType)
    );
  });

  return (
    <Card shadow="none" className="border border-default-200">
      <CardHeader
        className="pb-0 pt-1 px-4 cursor-pointer select-none"
        onClick={() => setIsCollapsed((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-3 h-3 shrink-0 text-default-600 transition-transform duration-150 ${isCollapsed ? '' : 'rotate-90'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 5l7 7-7 7"
            />
          </svg>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-default-800">
            {title}
          </h3>
        </div>
      </CardHeader>
      {!isCollapsed && (
        <CardBody className="flex flex-col gap-4 pt-3">
          {canEdit && !noEdit && (
            <div className="flex justify-start">
              <Checkbox
                size="sm"
                isSelected={isEditing}
                onValueChange={onEditToggle}
                classNames={{ label: 'text-xs text-default-700' }}
              >
                Edit
              </Checkbox>
            </div>
          )}
          {visibleKeys.map((key) => {
            const annotation = ANNOTATION_TEMPLATE[key];
            if (!annotation) return null;

            return (
              <MetadataField
                key={key}
                fieldKey={key}
                annotation={annotation}
                value={formValues[key] ?? ''}
                confidence={formValues[`${key}.$confidence`]}
                onChange={onChange}
                items={resolveListItems(key, parsedMeta)}
                forceEditable={isEditing}
                formValues={formValues}
              />
            );
          })}
        </CardBody>
      )}
    </Card>
  );
}

function resolveListItems(
  key: string,
  parsedMeta: ParsedMetadataYaml
): unknown[] | undefined {
  const model = parsedMeta.model;
  switch (key) {
    case 'model.authors': {
      return model?.authors;
    }
    case 'model.contacts': {
      return model?.contacts;
    }
    case 'model.publications': {
      return model?.publications;
    }
    case 'model.model_class': {
      return model?.model_class;
    }
    case 'model.formalism': {
      return model?.formalism;
    }
    case 'model.biology.species': {
      return model?.biology?.species;
    }
    case 'model.biology.infectious_agent': {
      return model?.biology?.infectious_agent;
    }
    case 'model.biology.health_condition': {
      return model?.biology?.health_condition;
    }
    case 'model.biology.biological_processes': {
      return model?.biology?.biological_processes;
    }
    case 'model.biology.molecular_entities': {
      return model?.biology?.molecular_entities;
    }
    case 'model.biology.proteins_genes': {
      return model?.biology?.proteins_genes;
    }
    case 'model.biology.topic_category': {
      return model?.biology?.topic_category;
    }
    case 'model.related_resources': {
      return model?.related_resources;
    }
    case 'model.funding': {
      return model?.funding;
    }
    case 'provenance.unmapped_fields': {
      return parsedMeta.provenance?.['unmapped_fields'] as
        | unknown[]
        | undefined;
    }
    default: {
      return undefined;
    }
  }
}
