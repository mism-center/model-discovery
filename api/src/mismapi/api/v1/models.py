import dataclasses
import logging
from typing import Any

from fastapi import APIRouter, Query
from mism_registry.enums import RunStatus
from mism_registry.resource import Resource

from mismapi.api.v1._run_helpers import resource_summary as _resource_summary
from mismapi.api.v1._run_helpers import run_detail as _run_detail
from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.core.deps import (
    ExecutionClientDep,
    RegistryServiceDep,
    SettingsDep,
    UploadSessionStoreServiceDep,
)
from mismapi.schemas.registry import (
    ExecuteRunRequest,
    ExecuteRunResponse,
    MetadataPackageFile,
    MetadataPackageRawResponse,
    MetadataPackageUpdateRequest,
    ModelRunDetailItem,
    ModelRunDetailsResponse,
    RegisterModelRequest,
    RegisterModelResponse,
    UpdateModelRequest,
    author_from_dto,
    author_to_dto,
    io_spec_from_dto,
    io_spec_to_dto,
    pub_from_dto,
    pub_to_dto,
)
from mismapi.schemas.search import ModelListItem, ModelListResponse
from mismapi.schemas.upload import UploadInitiatedResponse
from mismapi.utils import upload_dir

logger = logging.getLogger(__name__)

router = APIRouter()


def _model_list_item(r: Resource) -> ModelListItem:
    return ModelListItem(
        id=r.id,
        name=r.name,
        resource_type=r.resource_type.value,
        location_uri=r.location_uri,
        description=r.description,
        version=r.version,
        status=r.version_status.value,
        owner=r.owner,
        execution_type=r.execution_type.value if r.execution_type else None,
        execution_ref=r.execution_ref,
        io_spec=io_spec_to_dto(r.io_spec) if r.io_spec else None,
        format_tags=list(r.format_tags),
        authors=[author_to_dto(a) for a in r.authors],
        organization=r.organization,
        contact_email=r.contact_email,
        publications=[pub_to_dto(p) for p in r.publications],
        funding=list(r.funding),
        model_scales=list(r.model_scales),
        organisms=list(r.organisms),
        domains=list(r.domains),
        date_published=r.date_published,
        digest_sha256=r.digest_sha256,
        size_bytes=r.size_bytes,
        external_ids=dict(r.external_ids),
        license=r.license,
        metadata=dict(r.metadata),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _model_response(r: Resource) -> RegisterModelResponse:
    return RegisterModelResponse(
        id=r.id,
        name=r.name,
        resource_type=r.resource_type.value,
        location_uri=r.location_uri,
        description=r.description,
        version=r.version,
        status=r.version_status.value,
        registration_status=r.registration_status.value,
        owner=r.owner,
        execution_type=r.execution_type.value if r.execution_type else None,
        execution_ref=r.execution_ref,
        io_spec=io_spec_to_dto(r.io_spec) if r.io_spec else None,
        format_tags=list(r.format_tags),
        authors=[author_to_dto(a) for a in r.authors],
        organization=r.organization,
        contact_email=r.contact_email,
        publications=[pub_to_dto(p) for p in r.publications],
        funding=list(r.funding),
        model_scales=list(r.model_scales),
        organisms=list(r.organisms),
        domains=list(r.domains),
        date_published=r.date_published,
        digest_sha256=r.digest_sha256,
        size_bytes=r.size_bytes,
        external_ids=dict(r.external_ids),
        license=r.license,
        metadata=dict(r.metadata),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    service: RegistryServiceDep,
    name: str | None = Query(default=None, description="Substring match on model name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Model scales (any must match)"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ModelListResponse:

    resources = service.list_models(
        name_contains=name,
        owner=owner,
        tags=tags,
        organisms=organisms,
        scales=scales,
    )

    total = len(resources)
    page = resources[offset : offset + limit]

    return ModelListResponse(total=total, results=[_model_list_item(r) for r in page])


@router.get("/models/{model_id}", response_model=RegisterModelResponse)
async def get_model(
    model_id: str,
    service: RegistryServiceDep,
) -> RegisterModelResponse:
    """Fetch a single model by ID.

    Includes ``registration_status`` so the UI can poll annotation progress
    (DRAFT → ANNOTATING → PENDING_REVIEW / ANNOTATION_FAILED → APPROVED).
    The execution-platform's background poller writes these transitions directly
    to the shared registry; this endpoint reads the current value on demand.
    """
    resource = service.get_model(model_id)
    return _model_response(resource)


@router.post("/models", response_model=RegisterModelResponse, status_code=201)
async def create_model(
    payload: RegisterModelRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterModelResponse:

    resource = service.create_model(
        principal,
        name=payload.name,
        location_uri=payload.location_uri,
        execution_type=payload.execution_type,
        execution_ref=payload.execution_ref or "",
        io_spec=io_spec_from_dto(payload.io_spec) if payload.io_spec else None,
        description=payload.description,
        version=payload.version,
        format_tags=payload.format_tags,
        digest_sha256=payload.digest_sha256,
        size_bytes=payload.size_bytes,
        external_ids=payload.external_ids,
        license=payload.license,
        owner=payload.owner,
        metadata=payload.metadata,
        authors=[author_from_dto(a) for a in payload.authors],
        organization=payload.organization,
        contact_email=payload.contact_email,
        publications=[pub_from_dto(p) for p in payload.publications],
        funding=payload.funding,
        model_scales=payload.model_scales,
        organisms=payload.organisms,
        domains=payload.domains,
        date_published=payload.date_published,
    )

    return _model_response(resource)


@router.put("/models/{model_id}", response_model=RegisterModelResponse)
async def update_model(
    model_id: str,
    payload: UpdateModelRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterModelResponse:

    resource = service.update_model(
        principal,
        model_id=model_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        owner=payload.owner,
        location_uri=payload.location_uri,
        execution_type=payload.execution_type,
        execution_ref=payload.execution_ref,
        io_spec=io_spec_from_dto(payload.io_spec) if payload.io_spec else None,
        format_tags=payload.format_tags,
        digest_sha256=payload.digest_sha256,
        size_bytes=payload.size_bytes,
        external_ids=payload.external_ids,
        license=payload.license,
        metadata=payload.metadata,
        authors=[author_from_dto(a) for a in payload.authors]
        if payload.authors is not None
        else None,
        organization=payload.organization,
        contact_email=payload.contact_email,
        publications=[pub_from_dto(p) for p in payload.publications]
        if payload.publications is not None
        else None,
        funding=payload.funding,
        model_scales=payload.model_scales,
        organisms=payload.organisms,
        domains=payload.domains,
        date_published=payload.date_published,
    )

    return _model_response(resource)


@router.post("/models/{model_id}/upload", response_model=UploadInitiatedResponse)
async def initiate_model_file_upload(
    model_id: str,
    settings: SettingsDep,
    upload_session_store: UploadSessionStoreServiceDep,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> UploadInitiatedResponse:

    resource = service.get_resource_and_assert_ownership(principal, resource_id=model_id)
    allowed_path = upload_dir(model_id, resource.version)
    token = await upload_session_store.mint_upload_token(
        principal.subject,
        settings.upload_max_bytes,
        allowed_path,
    )

    return UploadInitiatedResponse(
        upload_server_base_url=settings.tusd_base_url,
        resource_id=model_id,
        token=token,
    )


@router.get("/models/{model_id}/metadata-package", response_model=None)
async def get_model_metadata_package(
    model_id: str,
    service: RegistryServiceDep,
) -> dict[str, Any]:
    """Parse the model's annotation ``metadata-package`` into a Resource preview.

    Looks for ``<model_id>/<version>/metadata-package/`` on the storage mount and
    maps its ``metadata.yaml`` + ``execution.yaml`` onto a Resource (values only,
    not persisted). 404 if the package is absent, 400 if it can't be parsed.
    """
    resource = service.parse_metadata_package(model_id)
    # asdict gives full nested detail (io, dependencies, ...); FastAPI's encoder
    # turns the enums into their string values and datetimes into ISO strings.
    return dataclasses.asdict(resource)


def _raw_response(model_id: str, files: list[tuple[str, str]]) -> MetadataPackageRawResponse:
    return MetadataPackageRawResponse(
        model_id=model_id,
        files=[MetadataPackageFile(filename=name, content=content) for name, content in files],
    )


@router.get("/models/{model_id}/metadata-package/raw", response_model=MetadataPackageRawResponse)
async def get_model_metadata_package_raw(
    model_id: str,
    service: RegistryServiceDep,
) -> MetadataPackageRawResponse:
    """Return the model's raw metadata-package YAML files as review sections."""
    return _raw_response(model_id, service.read_metadata_package_raw(model_id))


@router.put("/models/{model_id}/metadata-package/raw", response_model=MetadataPackageRawResponse)
async def update_model_metadata_package_raw(
    model_id: str,
    payload: MetadataPackageUpdateRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> MetadataPackageRawResponse:
    """Write edited raw YAML back to the metadata-package and return the result."""
    files = service.write_metadata_package_raw(
        principal,
        model_id=model_id,
        files=[(f.filename, f.content) for f in payload.files],
    )
    return _raw_response(model_id, files)


@router.post(
    "/models/{model_id}/runs",
    response_model=ExecuteRunResponse,
    status_code=201,
)
async def execute_run(
    model_id: str,
    payload: ExecuteRunRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
    execution_client: ExecutionClientDep,
) -> ExecuteRunResponse:
    """Create a run and immediately trigger execution on the Execution API."""

    # 1. Register the run in the DAL (same as create_run)
    run = service.create_run(
        principal,
        model_id=model_id,
        input_resource_ids=payload.input_resource_ids,
        parameters=payload.parameters,
        triggered_by=payload.triggered_by,
        notes=payload.notes,
    )

    # 2. Forward to Execution API
    if payload.mode == "interactive":
        exec_response = await execution_client.launch_interactive(run.id)
    else:
        exec_response = await execution_client.launch_batch(run.id)

    logger.info(
        "Executed run %s for model %s (mode=%s) by %s",
        run.id,
        model_id,
        payload.mode,
        principal.subject,
    )

    return ExecuteRunResponse(
        id=run.id,
        model_id=run.model_id,
        model_version=run.model_version,
        status=run.status.value,
        input_resource_ids=list(run.input_resource_ids),
        created_at=run.created_at,
        execution=exec_response,
    )


# ── GET /models/{model_id}/runs ─────────────────────────────────


@router.get("/models/{model_id}/runs", response_model=ModelRunDetailsResponse)
async def list_model_runs(
    model_id: str,
    service: RegistryServiceDep,
    status: RunStatus | None = Query(
        default=None, description="Optional filter — only include runs with this status."
    ),
) -> ModelRunDetailsResponse:
    """Fetch all runs for a model, enriched with hydrated input/output resources.

    Designed to populate the UI's "Model Runs" page in a single call.
    """
    summary = service.get_model_run_details(model_id=model_id, status=status)

    runs = [
        ModelRunDetailItem(
            run=_run_detail(detail.run),
            input_resources=[_resource_summary(r) for r in detail.input_resources],
            output_resources=[_resource_summary(r) for r in detail.output_resources],
        )
        for detail in summary.runs
    ]

    return ModelRunDetailsResponse(
        model=_resource_summary(summary.model),
        runs=runs,
        total=len(runs),
    )
