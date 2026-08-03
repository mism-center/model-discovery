import { useMemo, useState } from 'react';
import { parse as yamlParse, stringify as yamlStringify } from 'yaml';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Chip,
  Tab,
  Tabs,
} from '@heroui/react';

import type {
  AnnotationTemplate,
  FormValues,
  ParsedMetadataYaml,
} from './metadata-types';
import { ANNOTATION_TEMPLATE } from './metadata-template';
import {
  applyFormValuesToMetadata,
  extractFormValues,
} from './metadata-extractor';
import type { ParsedExecutionYaml } from './execution-types';
import { EXECUTION_TEMPLATE } from './execution-template';
import {
  applyFormValuesToExecution,
  extractExecutionFormValues,
} from './execution-extractor';
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
  'list-entry-point',
  'list-container',
  'list-dep',
]);

// Extracts the quoted field path from a backend warning string, e.g.
// "metadata.yaml: 'model.publications[0].title' is missing or empty; entry
// skipped" -> "model.publications[0].title". Returns null for warnings with
// no quoted field path (e.g. the generic whole-package parse-failure notice).
function extractWarningFieldPath(warning: string): string | null {
  const match = /'([^']+)'/.exec(warning);
  return match ? match[1] : null;
}

// Maps a warning's field path onto the section fieldKey it belongs to, e.g.
// "model.publications[0].title" -> "model.publications", so it can be
// matched against a FieldSection's fieldKeys.
function warningSectionKey(warning: string): string | null {
  const path = extractWarningFieldPath(warning);
  return path ? path.split('[')[0] : null;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function MetadataFormViewer({
  modelId,
  rawFiles,
  onSaved,
  onSaveError,
  annotationFiles,
}: MetadataFormViewerProps) {
  // ── metadata.yaml ──
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

  // ── execution.yaml ──
  const { parsedExec, execContent } = useMemo(() => {
    const execFile = rawFiles.find((f) => f.filename === 'execution.yaml');
    const execRaw = execFile?.content ?? '';

    let exec: ParsedExecutionYaml = {};
    try {
      exec = (yamlParse(execRaw) as ParsedExecutionYaml | null) ?? {};
    } catch {
      // keep empty — raw tab will still show original
    }

    return { parsedExec: exec, execContent: execRaw };
  }, [rawFiles]);

  // ── metadata form state ──
  const [formValues, setFormValues] = useState<FormValues>(() =>
    extractFormValues(parsedMeta)
  );
  const [sectionEditing, setSectionEditing] = useState<Record<string, boolean>>(
    {}
  );
  const [isDirty, setIsDirty] = useState(false);

  // ── execution form state ──
  const [execFormValues, setExecFormValues] = useState<FormValues>(() =>
    extractExecutionFormValues(parsedExec)
  );
  const [execSectionEditing, setExecSectionEditing] = useState<
    Record<string, boolean>
  >({});
  const [isExecDirty, setIsExecDirty] = useState(false);

  const [savedMetaContent, setSavedMetaContent] = useState<string | null>(null);
  const [savedExecContent, setSavedExecContent] = useState<string | null>(null);

  const [saveState, setSaveState] = useState<
    'idle' | 'saving' | 'saved' | 'error'
  >('idle');
  const [saveWarnings, setSaveWarnings] = useState<string[]>([]);

  function handleFieldChange(key: string, value: string) {
    setFormValues((prev) => ({ ...prev, [key]: value }));
    setIsDirty(true);
    setSaveState('idle');
    setSaveWarnings([]);
  }

  function handleExecFieldChange(key: string, value: string) {
    setExecFormValues((prev) => ({ ...prev, [key]: value }));
    setIsExecDirty(true);
    setSaveState('idle');
    setSaveWarnings([]);
  }

  async function handleApprove() {
    setSaveState('saving');
    setSaveWarnings([]);

    const updatedMeta = applyFormValuesToMetadata(parsedMeta, formValues);
    const newMetaContent = metaContent
      ? yamlStringify(updatedMeta, { lineWidth: 120 })
      : metaContent;

    const files: { filename: string; content: string }[] = [
      { filename: 'metadata.yaml', content: newMetaContent },
    ];

    let newExecContent = '';
    if (execContent) {
      const updatedExec = applyFormValuesToExecution(
        parsedExec,
        execFormValues
      );
      newExecContent = yamlStringify(updatedExec, { lineWidth: 120 });
      files.push({ filename: 'execution.yaml', content: newExecContent });
    }

    try {
      const res = await fetch(
        `/api/v1/models/${encodeURIComponent(modelId)}/metadata-package/raw`,
        {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ files }),
        }
      );
      if (!res.ok) {
        const detail = await res.text();
        setSaveState('error');
        onSaveError(detail || `Save failed (${res.status.toString()})`);
        return;
      }
      const payload = (await res.json()) as { warnings?: string[] };
      setSaveState('saved');
      setSaveWarnings(payload.warnings ?? []);
      setIsDirty(false);
      setIsExecDirty(false);
      setSavedMetaContent(newMetaContent);
      if (newExecContent) setSavedExecContent(newExecContent);
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
          tabContent:
            'text-default-800 group-data-[selected=true]:text-foreground group-data-[hover-unselected=true]:font-bold',
          panel: 'pt-0',
        }}
      >
        {/* ── Metadata tab ── */}
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
                  noEdit: true,
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
                warnings={saveWarnings}
              />
            ))}
          </div>
        </Tab>

        {/* ── Execution tab ── */}
        <Tab key="execution" title="Execution">
          <div className="flex flex-col gap-4">
            {(
              [
                {
                  title: 'Overview',
                  noEdit: false,
                  fieldKeys: [
                    'execution.status',
                    'execution.language.name',
                    'execution.language.version_constraint',
                    'execution.language.iri',
                    'execution.language.ontology',
                    'execution.environment_kind',
                    'execution.notes',
                  ],
                },
                {
                  title: 'Entry Points',
                  noEdit: false,
                  fieldKeys: ['execution.entry_points'],
                },
                {
                  title: 'Dependencies',
                  noEdit: false,
                  fieldKeys: [
                    'execution.dependencies.runtime',
                    'execution.dependencies.optional',
                    'execution.dependencies.system',
                  ],
                },
                {
                  title: 'Containers',
                  noEdit: false,
                  fieldKeys: ['execution.containers'],
                },
                {
                  title: 'Compute',
                  noEdit: false,
                  fieldKeys: [
                    'execution.compute.gpu_required',
                    'execution.compute.cpu_cores',
                    'execution.compute.memory_gb',
                    'execution.compute.parallelism',
                    'execution.compute.typical_runtime',
                  ],
                },
                {
                  title: 'Tests',
                  noEdit: true,
                  fieldKeys: [
                    'execution.tests.framework',
                    'execution.tests.invocation',
                  ],
                },
                {
                  title: 'I/O — Inputs',
                  noEdit: false,
                  fieldKeys: [
                    'io.inputs.parameters',
                    'io.inputs.initial_conditions',
                    'io.inputs.data_inputs',
                  ],
                },
                {
                  title: 'I/O — Outputs',
                  noEdit: false,
                  fieldKeys: ['io.outputs'],
                },
                {
                  title: 'Protocol',
                  noEdit: false,
                  fieldKeys: [
                    'io.experiment_protocol.description',
                    'io.experiment_protocol.timestep',
                    'io.experiment_protocol.duration',
                    'io.experiment_protocol.observables',
                  ],
                },
                {
                  title: 'Provenance',
                  noEdit: true,
                  fieldKeys: [
                    'exec_provenance.annotated_at',
                    'exec_provenance.annotated_by',
                    'exec_provenance.human_review_required',
                    'exec_provenance.notes',
                  ],
                },
              ] as const
            ).map(({ title, fieldKeys, noEdit }) => (
              <FieldSection
                key={title}
                title={title}
                fieldKeys={[...fieldKeys]}
                formValues={execFormValues}
                parsedMeta={{}}
                onChange={handleExecFieldChange}
                isEditing={execSectionEditing[title] ?? false}
                onEditToggle={(v) =>
                  setExecSectionEditing((prev) => ({ ...prev, [title]: v }))
                }
                noEdit={noEdit}
                template={EXECUTION_TEMPLATE}
                getItems={(key) => resolveExecutionListItems(key, parsedExec)}
                warnings={saveWarnings}
              />
            ))}
          </div>
        </Tab>

        {/* ── Raw Metadata YAML tab ── */}
        <Tab key="raw" title="Raw Metadata YAML">
          <div className="flex flex-col gap-3">
            {(savedMetaContent ?? metaContent) ? (
              <pre className="text-xs text-default-800 bg-default-100 rounded p-3 overflow-auto max-h-96 font-mono border border-default-200">
                {savedMetaContent ?? metaContent}
              </pre>
            ) : (
              <span className="text-xs text-default-400 italic">
                No metadata available
              </span>
            )}
          </div>
        </Tab>

        {/* ── Raw Execution YAML tab ── */}
        <Tab key="raw-execution" title="Raw Execution YAML">
          <div className="flex flex-col gap-3">
            {(savedExecContent ?? execContent) ? (
              <pre className="text-xs text-default-800 bg-default-100 rounded p-3 overflow-auto max-h-96 font-mono border border-default-200">
                {savedExecContent ?? execContent}
              </pre>
            ) : (
              <span className="text-xs text-default-400 italic">
                No execution data available
              </span>
            )}
          </div>
        </Tab>

        {/* ── Annotation Outputs tab ── */}
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
      </Tabs>

      {/* Approve action bar */}
      <div className="flex flex-col gap-2 pt-2 border-t border-default-200">
        <div className="flex items-center gap-2">
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
          {(isDirty || isExecDirty) && saveState === 'idle' && (
            <span className="text-xs text-default-800">Unsaved changes</span>
          )}
          {saveState === 'saved' && (
            <span className="text-xs text-success-800">Saved</span>
          )}
        </div>
        {saveState === 'saved' && saveWarnings.length > 0 && (
          <div className="rounded border border-warning-200 bg-warning-50 p-2 text-xs text-warning-800">
            <p className="font-semibold mb-1">
              Approved, but {saveWarnings.length} field
              {saveWarnings.length > 1 ? 's' : ''} could not be fully parsed:
            </p>
            <ul className="list-disc list-inside space-y-0.5">
              {saveWarnings.map((w) => (
                <li key={w} className="font-mono">
                  {w}
                </li>
              ))}
            </ul>
          </div>
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
  /** Template to use for field lookups; defaults to ANNOTATION_TEMPLATE. */
  template?: AnnotationTemplate;
  /** Override for list-item resolution; falls back to resolveListItems(key, parsedMeta). */
  getItems?: (key: string) => unknown[] | undefined;
  /** Approve-time warnings for fields that could not be fully parsed. */
  warnings?: string[];
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
  template,
  getItems,
  warnings = [],
}: FieldSectionProps) {
  const tmpl = template ?? ANNOTATION_TEMPLATE;
  const [isCollapsed, setIsCollapsed] = useState(true);
  const visibleKeys = fieldKeys.filter((key) => {
    const ann = tmpl[key];
    return ann !== undefined && !ann.hidden;
  });

  if (visibleKeys.length === 0) return null;

  const needsAttention = useMemo(() => {
    const allKeys = Object.keys(formValues);
    for (const key of visibleKeys) {
      const conf = formValues[`${key}.$confidence`];
      if (conf && conf !== 'high') return true;
      for (const fvKey of allKeys) {
        if (
          fvKey.startsWith(`${key}[`) &&
          (fvKey.endsWith('].confidence') ||
            fvKey.endsWith('].mapping_confidence'))
        ) {
          const val = formValues[fvKey];
          if (val && val !== 'high') return true;
        }
      }
    }
    return false;
  }, [visibleKeys, formValues]);

  const sectionWarnings = useMemo(
    () =>
      warnings.filter((w) => {
        const key = warningSectionKey(w);
        return key !== null && visibleKeys.includes(key);
      }),
    [warnings, visibleKeys]
  );

  // Only show the Edit checkbox when at least one field would actually change
  // rendering when forceEditable is toggled (viewable fields with editable inputTypes).
  const canEdit = visibleKeys.some((key) => {
    const ann = tmpl[key];
    return (
      ann?.visibility === 'viewable' &&
      VIEWABLE_FORCE_EDITABLE_TYPES.has(ann.inputType)
    );
  });

  return (
    <Card shadow="none" className="border border-default-200">
      <CardHeader
        className="flex flex-col items-stretch gap-2 py-3 px-4 cursor-pointer select-none"
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
          {needsAttention && (
            <Chip size="sm" color="warning" variant="flat">
              Needs attention
            </Chip>
          )}
          {sectionWarnings.length > 0 && (
            <Chip size="sm" color="danger" variant="flat">
              {sectionWarnings.length} skipped
            </Chip>
          )}
        </div>
        {sectionWarnings.length > 0 && (
          <div
            className="rounded border border-danger-200 bg-danger-50 p-2 text-xs text-danger-800"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-semibold mb-1">
              {sectionWarnings.length} field
              {sectionWarnings.length > 1 ? 's' : ''} in this section could not
              be fully parsed and {sectionWarnings.length > 1 ? 'were' : 'was'}{' '}
              skipped:
            </p>
            <ul className="list-disc list-inside space-y-0.5">
              {sectionWarnings.map((w) => (
                <li key={w} className="font-mono">
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}
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
            const annotation = tmpl[key];
            if (!annotation) return null;

            const resolvedItems = getItems
              ? getItems(key)
              : resolveListItems(key, parsedMeta);

            return (
              <MetadataField
                key={key}
                fieldKey={key}
                annotation={annotation}
                value={formValues[key] ?? ''}
                confidence={formValues[`${key}.$confidence`]}
                onChange={onChange}
                items={resolvedItems}
                forceEditable={isEditing}
                getFormValue={(k) => formValues[k] ?? ''}
                formValues={formValues}
              />
            );
          })}
        </CardBody>
      )}
    </Card>
  );
}

// ── resolveListItems (metadata.yaml) ─────────────────────────────────────────

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

// ── resolveExecutionListItems (execution.yaml) ────────────────────────────────

function resolveExecutionListItems(
  key: string,
  parsedExec: ParsedExecutionYaml
): unknown[] | undefined {
  const exec = parsedExec.execution;
  const io = parsedExec.io;
  switch (key) {
    case 'execution.entry_points': {
      return exec?.entry_points;
    }
    case 'execution.dependencies.runtime': {
      return exec?.dependencies?.runtime;
    }
    case 'execution.dependencies.optional': {
      return exec?.dependencies?.optional;
    }
    case 'execution.dependencies.system': {
      return exec?.dependencies?.system;
    }
    case 'execution.containers': {
      return exec?.containers;
    }
    case 'io.inputs.parameters': {
      return io?.inputs?.parameters;
    }
    case 'io.inputs.initial_conditions': {
      return io?.inputs?.initial_conditions;
    }
    case 'io.inputs.data_inputs': {
      return io?.inputs?.data_inputs;
    }
    case 'io.outputs': {
      return io?.outputs;
    }
    case 'io.experiment_protocol.observables': {
      return io?.experiment_protocol?.observables;
    }
    default: {
      return undefined;
    }
  }
}
