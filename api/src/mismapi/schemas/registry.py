from datetime import date, datetime
from typing import Any, Literal

from mism_registry import ExecutionType
from mism_registry.types import (
    Argument,
    Author,
    Compute,
    Contact,
    Container,
    Dependency,
    EntryPoint,
    IODetail,
    IOSlot,
    IOSpec,
    Publication,
    RelatedResource,
    TestSpec,
)
from pydantic import BaseModel, Field, field_validator, model_validator

from mismapi.core.file_storage import validate_location_uri

# ── Nested DTOs ──────────────────────────────────────────────────────


class AuthorDTO(BaseModel):
    name: str
    orcid: str = ""
    affiliation: str = ""
    role: str = ""


class PublicationDTO(BaseModel):
    title: str
    doi: str = ""
    pmid: str = ""
    url: str = ""
    citation: str = ""


class ContactDTO(BaseModel):
    """How to reach someone about the model now (`Resource.contacts`)."""

    name: str
    role: str = ""
    email: str = ""
    affiliation: str = ""


class RelatedResourceDTO(BaseModel):
    """A linked prior model or data source (`Resource.related_resources`).

    The only provenance link the registry stores — `qualifier` carries the
    relationship (e.g. `bqmodel:isDerivedFrom`, `bqbiol:isVersionOf`).
    """

    qualifier: str
    scheme: str = ""
    value: str = ""


class IOSlotDTO(BaseModel):
    name: str
    tags: list[str] = Field(default_factory=list)
    required: bool = True
    description: str = ""


class IOSpecDTO(BaseModel):
    inputs: list[IOSlotDTO] = Field(default_factory=list)
    outputs: list[IOSlotDTO] = Field(default_factory=list)
    parameters_schema: dict[str, Any] | None = None


class DependencyDTO(BaseModel):
    name: str
    version_constraint: str = ""
    kind: str = "runtime"
    group: str = ""


class ContainerDTO(BaseModel):
    kind: str
    file: str = ""
    image_name: str = ""
    registry: str = ""


class ComputeDTO(BaseModel):
    cpu_cores: int | None = None
    memory_gb: float | None = None
    gpu_required: bool | None = None
    parallelism: str = ""
    typical_runtime: float | None = None
    typical_runtime_unit: str = ""


class ArgumentDTO(BaseModel):
    """A documented argument to an entry-point command."""

    name: str
    description: str = ""
    default: Any = None
    enums: list[str] | None = None  # allowed values, if constrained
    data_type: str = ""  # e.g. "int", "str", "path", "bool"
    position: int = 0  # positional index; 0 = unassigned (option/flag)
    user_can_override: bool | None = None


# ── Section C: rich I/O characterization (`Resource.io`) ─────────────
#
# Distinct from `io_spec`, which is the machine handshake used to validate a run
# (slot names + tags + a JSON Schema). This is the *human* description of what
# the model consumes and produces — units, biological meaning, protocol — and it
# is the richest metadata a characterized model carries. It was absent from the
# detail response entirely, so the page had nothing real to show under I/O.


class ParameterDTO(BaseModel):
    name: str
    description: str = ""
    default_value: Any = None
    unit: str = ""
    biological_meaning: str = ""


class InitialConditionDTO(BaseModel):
    name: str
    value: Any = None
    unit: str = ""


class DataInputDTO(BaseModel):
    name: str
    purpose: str = ""
    format: str = ""
    required: bool = True


class OutputDTO(BaseModel):
    name: str
    description: str = ""
    quantity_kind: str = ""
    unit: str = ""
    format: str = ""
    destination: str = ""


class ExperimentProtocolDTO(BaseModel):
    description: str = ""
    timestep: float | None = None
    timestep_unit: str = ""
    duration: float | None = None
    duration_unit: str = ""
    observables: list[str] = Field(default_factory=list)


class IODetailDTO(BaseModel):
    parameters: list[ParameterDTO] = Field(default_factory=list)
    initial_conditions: list[InitialConditionDTO] = Field(default_factory=list)
    data_inputs: list[DataInputDTO] = Field(default_factory=list)
    outputs: list[OutputDTO] = Field(default_factory=list)
    experiment_protocol: ExperimentProtocolDTO | None = None


class EntryPointDTO(BaseModel):
    command: str
    purpose: str = ""
    arguments: list[ArgumentDTO] = Field(default_factory=list)


class TestSpecDTO(BaseModel):
    framework: str = ""
    invocation: str = ""


# ── DTO ↔ dataclass converters ───────────────────────────────────────


def author_from_dto(dto: AuthorDTO) -> Author:
    return Author(name=dto.name, orcid=dto.orcid, affiliation=dto.affiliation, role=dto.role)


def pub_from_dto(dto: PublicationDTO) -> Publication:
    return Publication(
        title=dto.title, doi=dto.doi, pmid=dto.pmid, url=dto.url, citation=dto.citation
    )


def io_slot_from_dto(dto: IOSlotDTO) -> IOSlot:
    return IOSlot(
        name=dto.name, tags=tuple(dto.tags), required=dto.required, description=dto.description
    )


def io_spec_from_dto(dto: IOSpecDTO) -> IOSpec:
    return IOSpec(
        inputs=tuple(io_slot_from_dto(s) for s in dto.inputs),
        outputs=tuple(io_slot_from_dto(s) for s in dto.outputs),
        parameters_schema=dto.parameters_schema,
    )


def author_to_dto(a: Author) -> AuthorDTO:
    return AuthorDTO(name=a.name, orcid=a.orcid, affiliation=a.affiliation, role=a.role)


def pub_to_dto(p: Publication) -> PublicationDTO:
    return PublicationDTO(title=p.title, doi=p.doi, pmid=p.pmid, url=p.url, citation=p.citation)


def contact_to_dto(c: Contact) -> ContactDTO:
    return ContactDTO(name=c.name, role=c.role, email=c.email, affiliation=c.affiliation)


def related_resource_to_dto(r: RelatedResource) -> RelatedResourceDTO:
    return RelatedResourceDTO(qualifier=r.qualifier, scheme=r.scheme, value=r.value)


def io_detail_to_dto(io: IODetail) -> IODetailDTO:
    protocol = io.experiment_protocol
    return IODetailDTO(
        parameters=[
            ParameterDTO(
                name=p.name,
                description=p.description,
                default_value=p.default_value,
                unit=p.unit,
                biological_meaning=p.biological_meaning,
            )
            for p in io.parameters
        ],
        initial_conditions=[
            InitialConditionDTO(name=c.name, value=c.value, unit=c.unit)
            for c in io.initial_conditions
        ],
        data_inputs=[
            DataInputDTO(name=d.name, purpose=d.purpose, format=d.format, required=d.required)
            for d in io.data_inputs
        ],
        outputs=[
            OutputDTO(
                name=o.name,
                description=o.description,
                quantity_kind=o.quantity_kind,
                unit=o.unit,
                format=o.format,
                destination=o.destination,
            )
            for o in io.outputs
        ],
        experiment_protocol=(
            ExperimentProtocolDTO(
                description=protocol.description,
                timestep=protocol.timestep,
                timestep_unit=protocol.timestep_unit,
                duration=protocol.duration,
                duration_unit=protocol.duration_unit,
                observables=list(protocol.observables),
            )
            if protocol is not None
            else None
        ),
    )


def io_slot_to_dto(s: IOSlot) -> IOSlotDTO:
    return IOSlotDTO(name=s.name, tags=list(s.tags), required=s.required, description=s.description)


def io_spec_to_dto(spec: IOSpec) -> IOSpecDTO:
    return IOSpecDTO(
        inputs=[io_slot_to_dto(s) for s in spec.inputs],
        outputs=[io_slot_to_dto(s) for s in spec.outputs],
        parameters_schema=spec.parameters_schema,
    )


# Read-only converters (details response); no *_from_dto counterparts because
# these fields are written through the metadata-package path, not the API.


def dependency_to_dto(d: Dependency) -> DependencyDTO:
    return DependencyDTO(
        name=d.name, version_constraint=d.version_constraint, kind=d.kind, group=d.group
    )


def container_to_dto(c: Container) -> ContainerDTO:
    return ContainerDTO(kind=c.kind, file=c.file, image_name=c.image_name, registry=c.registry)


def compute_to_dto(c: Compute) -> ComputeDTO:
    return ComputeDTO(
        cpu_cores=c.cpu_cores,
        memory_gb=c.memory_gb,
        gpu_required=c.gpu_required,
        parallelism=c.parallelism,
        typical_runtime=c.typical_runtime,
        typical_runtime_unit=c.typical_runtime_unit,
    )


def argument_to_dto(a: Argument) -> ArgumentDTO:
    return ArgumentDTO(
        name=a.name,
        description=a.description,
        default=a.default,
        enums=list(a.enums) if a.enums is not None else None,
        data_type=a.data_type or "",
        position=a.position or 0,
        user_can_override=a.user_can_override,
    )


def entry_point_to_dto(e: EntryPoint) -> EntryPointDTO:
    return EntryPointDTO(
        command=e.command,
        purpose=e.purpose,
        arguments=[argument_to_dto(a) for a in e.arguments],
    )


def test_spec_to_dto(t: TestSpec) -> TestSpecDTO:
    return TestSpecDTO(framework=t.framework, invocation=t.invocation)


# ── Shared field mixin (used in request & response bodies) ───────────


class _AttributionFields(BaseModel):
    """Authorship & attribution fields shared across create/update requests."""

    authors: list[AuthorDTO] = Field(default_factory=list)
    organization: str = ""
    contact_email: str = ""
    publications: list[PublicationDTO] = Field(default_factory=list)
    funding: list[str] = Field(default_factory=list)


class _ScientificFields(BaseModel):
    """Scientific-context fields shared across create/update requests."""

    model_scales: list[str] = Field(default_factory=list)
    organisms: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    date_published: date | None = None


class _IntegrityFields(BaseModel):
    """Location & integrity fields shared across create/update requests."""

    digest_sha256: str = ""
    size_bytes: int | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    license: str = ""


# ── Model schemas ────────────────────────────────────────────────────


class RegisterModelRequest(_AttributionFields, _ScientificFields, _IntegrityFields):
    name: str
    location_uri: str
    execution_type: ExecutionType
    execution_ref: str | None = None
    io_spec: IOSpecDTO | None = None
    description: str = ""
    version: str = ""
    format_tags: list[str] = Field(default_factory=list)
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Reject location_uris the download endpoint cannot resolve (only iRODS
    # URIs and plain paths are servable). Empty string is allowed so callers
    # can defer to the upload flow, which stamps the real URI in post-finish.
    _validate_location_uri = field_validator("location_uri")(
        lambda cls, v: validate_location_uri(v)
    )


class RegisterModelResponse(BaseModel):
    id: str
    name: str
    resource_type: str
    location_uri: str
    description: str = ""
    version: str = ""
    status: str
    registration_status: str
    owner: str = ""
    execution_type: str | None = None
    execution_ref: str = ""
    io_spec: IOSpecDTO | None = None
    # Execution recipe (populated from the annotation metadata-package): the
    # entry points a run can select and the container(s) it runs in.
    entry_points: list[EntryPointDTO] = Field(default_factory=list)
    containers: list[ContainerDTO] = Field(default_factory=list)
    format_tags: list[str] = Field(default_factory=list)
    # Authorship & attribution
    authors: list[AuthorDTO] = Field(default_factory=list)
    organization: str = ""
    contact_email: str = ""
    publications: list[PublicationDTO] = Field(default_factory=list)
    funding: list[str] = Field(default_factory=list)
    # Scientific context
    model_scales: list[str] = Field(default_factory=list)
    organisms: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    date_published: date | None = None
    # Integrity
    digest_sha256: str = ""
    size_bytes: int | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    license: str = ""
    # System
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    # Metadata-review tracking (MISM-291) — who reviewed it and why it was
    # rejected, if it was. Empty/None until a reviewer has acted.
    metadata_reviewed_by: str = ""
    metadata_reviewed_at: datetime | None = None
    metadata_rejection_reason: str = ""
    # Dockerfile/image-review tracking (MISM-291) — mirrors the metadata-review
    # fields above, for the IMAGE_CHECK workflow (steps i-k). "not_applicable"
    # until a container recipe is submitted; who vetted it and why it was
    # rejected, if it was.
    image_review_status: str = "not_applicable"
    image_reviewed_by: str = ""
    image_reviewed_at: datetime | None = None
    image_rejection_reason: str = ""


class ModelDetailResponse(RegisterModelResponse):
    """Full detail view of a model (GET /models/{id} only).

    Extends the registration response with the characterization fields
    populated by the metadata-package workflow (schema.md Sections A/B).
    Create/update endpoints keep returning ``RegisterModelResponse``.
    """

    # Model characterization (schema.md Section A)
    short_description: str = ""
    model_class: list[str] = Field(default_factory=list)
    formalism: list[str] = Field(default_factory=list)
    determinism: str = "unknown"
    time_dynamics: str = "unknown"
    spatial: str = "unknown"
    multiscale: bool | None = None
    # Biology
    infectious_agents: list[str] = Field(default_factory=list)
    health_conditions: list[str] = Field(default_factory=list)
    biological_processes: list[str] = Field(default_factory=list)
    molecular_entities: list[str] = Field(default_factory=list)
    proteins_genes: list[str] = Field(default_factory=list)
    # Execution characterization (schema.md Section B)
    execution_status: str = ""
    language_name: str = ""
    language_version: str = ""
    execution_notes: str = ""
    dependencies: list[DependencyDTO] = Field(default_factory=list)
    containers: list[ContainerDTO] = Field(default_factory=list)
    compute: ComputeDTO | None = None
    entry_points: list[EntryPointDTO] = Field(default_factory=list)
    tests: TestSpecDTO | None = None
    # Rich I/O characterization (schema.md Section C) — the human-readable
    # counterpart to `io_spec`, and the richest data a characterized model has.
    io: IODetailDTO | None = None
    # Attribution and provenance the response previously dropped.
    # `related_resources` is the registry's only "derived from / version of" link.
    contacts: list[ContactDTO] = Field(default_factory=list)
    related_resources: list[RelatedResourceDTO] = Field(default_factory=list)


class UpdateModelRequest(_AttributionFields, _ScientificFields, _IntegrityFields):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    owner: str | None = None
    location_uri: str | None = None
    execution_type: ExecutionType | None = None
    execution_ref: str | None = None
    io_spec: IOSpecDTO | None = None
    format_tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    # Attribution nullables (None = no-op, same pattern as other optional update fields)
    authors: list[AuthorDTO] | None = None  # type: ignore[assignment]
    organization: str | None = None  # type: ignore[assignment]
    contact_email: str | None = None  # type: ignore[assignment]
    publications: list[PublicationDTO] | None = None  # type: ignore[assignment]
    funding: list[str] | None = None  # type: ignore[assignment]
    # Scientific nullables
    model_scales: list[str] | None = None  # type: ignore[assignment]
    organisms: list[str] | None = None  # type: ignore[assignment]
    domains: list[str] | None = None  # type: ignore[assignment]
    date_published: date | None = None
    # Integrity nullables
    digest_sha256: str | None = None  # type: ignore[assignment]
    size_bytes: int | None = None
    external_ids: dict[str, str] | None = None  # type: ignore[assignment]
    license: str | None = None  # type: ignore[assignment]

    # None = no-op (don't touch location_uri); empty string allowed (upload
    # flow will reconcile). Reject schemes the download endpoint can't resolve.
    _validate_location_uri = field_validator("location_uri")(
        lambda cls, v: v if v is None else validate_location_uri(v)
    )


# ── Dataset schemas ──────────────────────────────────────────────────


class RegisterDatasetRequest(_AttributionFields, _ScientificFields, _IntegrityFields):
    name: str
    location_uri: str
    description: str = ""
    version: str = ""
    owner: str = ""
    format_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _validate_location_uri = field_validator("location_uri")(
        lambda cls, v: validate_location_uri(v)
    )


class RegisterDatasetResponse(BaseModel):
    id: str
    name: str
    resource_type: str
    location_uri: str
    description: str = ""
    version: str = ""
    status: str
    owner: str = ""
    format_tags: list[str] = Field(default_factory=list)
    # Authorship & attribution
    authors: list[AuthorDTO] = Field(default_factory=list)
    organization: str = ""
    contact_email: str = ""
    publications: list[PublicationDTO] = Field(default_factory=list)
    funding: list[str] = Field(default_factory=list)
    # Scientific context
    model_scales: list[str] = Field(default_factory=list)
    organisms: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    date_published: date | None = None
    # Integrity
    digest_sha256: str = ""
    size_bytes: int | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    license: str = ""
    # System
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UpdateDatasetRequest(_AttributionFields, _ScientificFields, _IntegrityFields):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    owner: str | None = None
    location_uri: str | None = None
    format_tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    # Attribution nullables
    authors: list[AuthorDTO] | None = None  # type: ignore[assignment]
    organization: str | None = None  # type: ignore[assignment]
    contact_email: str | None = None  # type: ignore[assignment]
    publications: list[PublicationDTO] | None = None  # type: ignore[assignment]
    funding: list[str] | None = None  # type: ignore[assignment]
    # Scientific nullables
    model_scales: list[str] | None = None  # type: ignore[assignment]
    organisms: list[str] | None = None  # type: ignore[assignment]
    domains: list[str] | None = None  # type: ignore[assignment]
    date_published: date | None = None
    # Integrity nullables
    digest_sha256: str | None = None  # type: ignore[assignment]
    size_bytes: int | None = None
    external_ids: dict[str, str] | None = None  # type: ignore[assignment]
    license: str | None = None  # type: ignore[assignment]

    _validate_location_uri = field_validator("location_uri")(
        lambda cls, v: v if v is None else validate_location_uri(v)
    )


# ── Run schemas ──────────────────────────────────────────────────────


class CreateRunRequest(BaseModel):
    input_resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    # Select one of the model's declared entry points by index. When set,
    # ``arguments`` (VALUES keyed by the entry point's declared arg names —
    # never command/flag strings) are validated against it. Injection defense
    # lives in the registry: the caller never supplies a raw command.
    entrypoint_index: int | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class CreateRunResponse(BaseModel):
    id: str
    model_id: str
    model_version: str = ""
    status: str
    input_resource_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class ExecuteRunRequest(BaseModel):
    """Create a run AND trigger execution on the Execution API."""

    input_resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    # Select one of the model's declared entry points by index. When set,
    # ``arguments`` (VALUES keyed by the entry point's declared arg names —
    # never command/flag strings) are validated against it. Injection defense
    # lives in the registry: the caller never supplies a raw command.
    entrypoint_index: int | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    mode: Literal["batch", "interactive"] = "batch"


class ExecuteRunResponse(BaseModel):
    """Combined response: run record + execution launch result."""

    id: str
    model_id: str
    model_version: str = ""
    status: str
    input_resource_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    execution: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw response from the Execution API (batch or interactive).",
    )


# ── Model run details (UI: model runs page) ──────────────────────────


class ResourceSummaryItem(BaseModel):
    """Lightweight summary of a Resource for embedding inside run detail responses."""

    id: str
    name: str
    resource_type: str
    location_uri: str
    description: str = ""
    version: str = ""
    status: str
    owner: str = ""
    format_tags: list[str] = Field(default_factory=list)
    # Authorship & attribution
    authors: list[AuthorDTO] = Field(default_factory=list)
    organization: str = ""
    contact_email: str = ""
    publications: list[PublicationDTO] = Field(default_factory=list)
    funding: list[str] = Field(default_factory=list)
    # Scientific context
    model_scales: list[str] = Field(default_factory=list)
    organisms: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    date_published: date | None = None
    # Integrity
    digest_sha256: str = ""
    size_bytes: int | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    license: str = ""
    # Execution
    execution_type: str | None = None
    execution_ref: str = ""
    io_spec: IOSpecDTO | None = None
    # Execution recipe (populated from the annotation metadata-package): the
    # entry points a run can select and the container(s) it runs in.
    entry_points: list[EntryPointDTO] = Field(default_factory=list)
    containers: list[ContainerDTO] = Field(default_factory=list)
    # System
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class RunDetailItem(BaseModel):
    """Full Run record as returned to the UI."""

    id: str
    model_id: str
    model_version: str = ""
    status: str
    input_resource_ids: list[str] = Field(default_factory=list)
    output_resource_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    # Entry point selected for this run + the container it was denormalized
    # onto (both null for runs created before entry-point selection existed).
    entrypoint: EntryPointDTO | None = None
    container: ContainerDTO | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str = ""
    log_uri: str = ""
    triggered_by: str = ""
    notes: str = ""
    created_at: datetime

    model_config = {"protected_namespaces": ()}


class ModelRunDetailItem(BaseModel):
    """A run enriched with hydrated input and output resources."""

    run: RunDetailItem
    input_resources: list[ResourceSummaryItem] = Field(default_factory=list)
    output_resources: list[ResourceSummaryItem] = Field(default_factory=list)


class ModelRunDetailsResponse(BaseModel):
    """All runs for a model, with the model summary and hydrated run details."""

    model: ResourceSummaryItem
    runs: list[ModelRunDetailItem] = Field(default_factory=list)
    total: int

    model_config = {"protected_namespaces": ()}


# ── User run history (UI: "My Runs" page) ────────────────────────────


class UserRunItem(BaseModel):
    """A single run in the cross-model "My Runs" list.

    Like ``ModelRunDetailItem`` but adds the run's ``model`` summary, since this
    is a global list where each row can belong to a different model.
    """

    model: ResourceSummaryItem
    run: RunDetailItem
    input_resources: list[ResourceSummaryItem] = Field(default_factory=list)
    output_resources: list[ResourceSummaryItem] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


class UserRunsResponse(BaseModel):
    """All runs triggered by the calling user, newest-first, hydrated."""

    runs: list[UserRunItem] = Field(default_factory=list)
    total: int

    model_config = {"protected_namespaces": ()}


class RunDetailResponse(BaseModel):
    """Single run, hydrated, with the latest execution-service status snapshot.

    Returned by GET /runs/{run_id}. The Discovery API calls the Execution API
    first so the exec service can perform its lazy DAL refresh; the run record
    here is then read from the DAL with that fresh state already applied.
    """

    run: RunDetailItem
    input_resources: list[ResourceSummaryItem] = Field(default_factory=list)
    output_resources: list[ResourceSummaryItem] = Field(default_factory=list)
    execution_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw response from the Execution service /api/v1/runs/{run_id} call.",
    )


# ── Resource files (download/listing) ────────────────────────────────


class ResourceFileItem(BaseModel):
    """One entry in a resource's artifact directory."""

    path: str = Field(description="Relative path from the resource directory root.")
    name: str = Field(description="Final path segment (basename).")
    size_bytes: int = Field(ge=0)
    is_dir: bool = False
    modified_at: datetime | None = None


class ResourceFilesResponse(BaseModel):
    """Listing of files for a resource."""

    resource_id: str
    location_uri: str
    files: list[ResourceFileItem] = Field(default_factory=list)
    total: int


# ── Metadata-package raw review ──────────────────────────────────────


class MetadataPackageFile(BaseModel):
    """One raw YAML file of a metadata-package, as a review section."""

    filename: str = Field(description="metadata.yaml or execution.yaml")
    content: str = Field(description="Raw file text.")


class MetadataPackageRawResponse(BaseModel):
    """The metadata-package's raw YAML files, one section per file."""

    model_id: str
    files: list[MetadataPackageFile] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking issues found while parsing the metadata-package "
        "(missing/empty required fields); the save still succeeded.",
    )


class MetadataPackageUpdateRequest(BaseModel):
    """Edited raw YAML files to write back to the metadata-package."""

    files: list[MetadataPackageFile] = Field(min_length=1)


class ReviewMetadataPackageRequest(BaseModel):
    """An UPLOAD_REVIEWER's approve/reject decision on a PENDING_REVIEW model
    (MISM-291)."""

    approve: bool
    reason: str = ""

    @model_validator(mode="after")
    def _require_reason_on_reject(self) -> "ReviewMetadataPackageRequest":
        if not self.approve and not self.reason.strip():
            raise ValueError("reason is required when approve is false")
        return self


class SubmitContainerImageRequest(BaseModel):
    """Submit (or resubmit) a built Dockerfile/image for IMAGE_CHECK review
    (MISM-291, workflow steps h/l). Resubmitting after an ``IMAGE_REJECTED``
    decision uses this same request — there is no separate "resubmit" shape."""

    kind: str
    file: str = ""
    image_name: str = ""
    registry: str = ""


class ReviewContainerImageRequest(BaseModel):
    """An IMAGE_CHECK holder's approve/reject decision on a
    PENDING_IMAGE_CHECK model's Dockerfile/image (MISM-291)."""

    approve: bool
    reason: str = ""

    @model_validator(mode="after")
    def _require_reason_on_reject(self) -> "ReviewContainerImageRequest":
        if not self.approve and not self.reason.strip():
            raise ValueError("reason is required when approve is false")
        return self
