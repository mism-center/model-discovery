from datetime import date, datetime
from typing import Any, Literal

from mism_registry import ExecutionType
from mism_registry.types import Author, IOSlot, IOSpec, Publication
from pydantic import BaseModel, Field, field_validator

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
    url: str = ""
    citation: str = ""


class IOSlotDTO(BaseModel):
    name: str
    tags: list[str] = Field(default_factory=list)
    required: bool = True
    description: str = ""


class IOSpecDTO(BaseModel):
    inputs: list[IOSlotDTO] = Field(default_factory=list)
    outputs: list[IOSlotDTO] = Field(default_factory=list)
    parameters_schema: dict[str, Any] | None = None


# ── DTO ↔ dataclass converters ───────────────────────────────────────


def author_from_dto(dto: AuthorDTO) -> Author:
    return Author(name=dto.name, orcid=dto.orcid, affiliation=dto.affiliation, role=dto.role)


def pub_from_dto(dto: PublicationDTO) -> Publication:
    return Publication(title=dto.title, doi=dto.doi, url=dto.url, citation=dto.citation)


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
    return PublicationDTO(title=p.title, doi=p.doi, url=p.url, citation=p.citation)


def io_slot_to_dto(s: IOSlot) -> IOSlotDTO:
    return IOSlotDTO(name=s.name, tags=list(s.tags), required=s.required, description=s.description)


def io_spec_to_dto(spec: IOSpec) -> IOSpecDTO:
    return IOSpecDTO(
        inputs=[io_slot_to_dto(s) for s in spec.inputs],
        outputs=[io_slot_to_dto(s) for s in spec.outputs],
        parameters_schema=spec.parameters_schema,
    )


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
    owner: str = ""
    execution_type: str | None = None
    execution_ref: str = ""
    io_spec: IOSpecDTO | None = None
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
    triggered_by: str = ""
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
    triggered_by: str = ""
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


class MetadataPackageUpdateRequest(BaseModel):
    """Edited raw YAML files to write back to the metadata-package."""

    files: list[MetadataPackageFile] = Field(min_length=1)
