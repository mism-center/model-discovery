import dataclasses
import logging
from typing import Any

from fastapi import APIRouter, Query
from mism_registry.enums import RunStatus
from mism_registry.resource import Resource
from mism_registry.types import Container

from mismapi.api.v1._authz import assert_model_visible, model_visible_to
from mismapi.api.v1._run_helpers import resource_summary as _resource_summary
from mismapi.api.v1._run_helpers import run_detail as _run_detail
from mismapi.auth.base import AuthenticatedPrincipalDep, OptionalPrincipalDep
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
    ModelDetailResponse,
    ModelRunDetailItem,
    ModelRunDetailsResponse,
    RegisterModelRequest,
    RegisterModelResponse,
    ReviewContainerImageRequest,
    ReviewMetadataPackageRequest,
    SubmitContainerImageRequest,
    UpdateModelRequest,
    author_from_dto,
    author_to_dto,
    compute_to_dto,
    contact_to_dto,
    container_to_dto,
    dependency_to_dto,
    entry_point_to_dto,
    io_detail_to_dto,
    io_spec_from_dto,
    io_spec_to_dto,
    pub_from_dto,
    pub_to_dto,
    related_resource_to_dto,
    test_spec_to_dto,
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
        entry_points=[entry_point_to_dto(e) for e in r.entry_points],
        containers=[container_to_dto(c) for c in r.containers],
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
        registration_status=r.registration_status.value,
        image_review_status=r.image_review_status.value,
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
        entry_points=[entry_point_to_dto(e) for e in r.entry_points],
        containers=[container_to_dto(c) for c in r.containers],
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
        metadata_reviewed_by=r.metadata_reviewed_by,
        metadata_reviewed_at=r.metadata_reviewed_at,
        metadata_rejection_reason=r.metadata_rejection_reason,
        image_review_status=r.image_review_status.value,
        image_reviewed_by=r.image_reviewed_by,
        image_reviewed_at=r.image_reviewed_at,
        image_rejection_reason=r.image_rejection_reason,
    )


def _model_detail_response(r: Resource) -> ModelDetailResponse:
    # `entry_points` and `containers` are deliberately not repeated below:
    # `RegisterModelResponse` carries them, so they arrive via `base` and passing
    # them again raises "got multiple values for keyword argument".
    base = _model_response(r).model_dump()
    return ModelDetailResponse(
        **base,
        # Model characterization (schema.md Section A)
        short_description=r.short_description,
        model_class=list(r.model_class),
        formalism=list(r.formalism),
        determinism=r.determinism,
        time_dynamics=r.time_dynamics,
        spatial=r.spatial,
        multiscale=r.multiscale,
        # Biology
        infectious_agents=list(r.infectious_agents),
        health_conditions=list(r.health_conditions),
        biological_processes=list(r.biological_processes),
        molecular_entities=list(r.molecular_entities),
        proteins_genes=list(r.proteins_genes),
        # Execution characterization (schema.md Section B)
        execution_status=r.execution_status,
        language_name=r.language_name,
        language_version=r.language_version,
        execution_notes=r.execution_notes,
        dependencies=[dependency_to_dto(d) for d in r.dependencies],
        compute=compute_to_dto(r.compute) if r.compute else None,
        tests=test_spec_to_dto(r.tests) if r.tests else None,
        # Rich I/O characterization (schema.md Section C) + the attribution and
        # provenance links the response previously dropped on the floor.
        io=io_detail_to_dto(r.io) if r.io else None,
        contacts=[contact_to_dto(c) for c in r.contacts],
        related_resources=[related_resource_to_dto(x) for x in r.related_resources],
    )


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    service: RegistryServiceDep,
    principal: OptionalPrincipalDep,
    name: str | None = Query(default=None, description="Substring match on model name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Model scales (any must match)"),
    registration_status: str | None = Query(
        default=None, description="Exact match on registration status"
    ),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ModelListResponse:
    resources = service.list_models(
        name_contains=name,
        owner=owner,
        tags=tags,
        organisms=organisms,
        scales=scales,
        registration_status=registration_status,
    )

    # Same visibility rule as GET /models/{model_id} and the search gate:
    # approved models are public, anything still in draft / annotating /
    # pending_review / rejected is visible only to its owner. Filtering before
    # pagination keeps `total` and the page contents consistent — counting
    # hidden rows would leak their existence through the count alone.
    visible = [r for r in resources if model_visible_to(r, principal)]

    total = len(visible)
    page = visible[offset : offset + limit]

    return ModelListResponse(total=total, results=[_model_list_item(r) for r in page])


@router.get("/models/{model_id}", response_model=ModelDetailResponse)
async def get_model(
    model_id: str,
    service: RegistryServiceDep,
    principal: OptionalPrincipalDep,
) -> ModelDetailResponse:
    """Fetch a single model by ID.

    Includes ``registration_status`` so the UI can poll annotation progress
    (DRAFT → ANNOTATING → PENDING_REVIEW / ANNOTATION_FAILED → APPROVED).
    The execution-platform's background poller writes these transitions directly
    to the shared registry; this endpoint reads the current value on demand.

    Returns the full detail view, including the characterization fields
    populated by the metadata-package workflow.

    Anonymous reads are allowed for approved models only. Anything still in
    draft / annotating / pending_review / rejected is visible solely to its
    owner, matching the gate the search path already applies — so an
    unapproved model's characterization can't be read by url-guessing. The
    uploader keeps polling their own draft because ``create_model`` stores
    ``owner = principal.subject``.
    """
    resource = service.get_model(model_id)
    assert_model_visible(resource, principal)
    return _model_detail_response(resource)


@router.post("/models", response_model=RegisterModelResponse, status_code=201)
async def create_model(
    payload: RegisterModelRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterModelResponse:
    resource = await service.create_model(
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


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: str,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> None:
    """Permanently delete a model and its on-disk annotation files."""
    service.delete_model(principal, model_id)


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
    not persisted). 404 if the package is absent, 400 if it can't be parsed at
    all; individual missing/empty fields are tolerated and reported in
    ``warnings`` instead.
    """
    resource, warnings = service.parse_metadata_package(model_id)
    # asdict gives full nested detail (io, dependencies, ...); FastAPI's encoder
    # turns the enums into their string values and datetimes into ISO strings.
    data = dataclasses.asdict(resource)
    data["warnings"] = warnings
    return data


def _raw_response(
    model_id: str, files: list[tuple[str, str]], warnings: list[str]
) -> MetadataPackageRawResponse:
    return MetadataPackageRawResponse(
        model_id=model_id,
        files=[MetadataPackageFile(filename=name, content=content) for name, content in files],
        warnings=warnings,
    )


@router.get("/models/{model_id}/metadata-package/raw", response_model=MetadataPackageRawResponse)
async def get_model_metadata_package_raw(
    model_id: str,
    service: RegistryServiceDep,
) -> MetadataPackageRawResponse:
    """Return the model's raw metadata-package YAML files as review sections."""
    return _raw_response(model_id, service.read_metadata_package_raw(model_id), [])


@router.put("/models/{model_id}/metadata-package/raw", response_model=MetadataPackageRawResponse)
async def update_model_metadata_package_raw(
    model_id: str,
    payload: MetadataPackageUpdateRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> MetadataPackageRawResponse:
    """Write edited raw YAML back to the metadata-package and return the result.

    Missing/empty fields on individual entries (an author with no name,
    etc.) are tolerated and reported in ``warnings``, not raised — see
    ``RegistryService.write_metadata_package_raw``. If the package fails to
    parse at all (the top-level ``model``/``execution`` structure itself is
    broken), this raises a 400 and the DB is left untouched. Approval/
    rejection is not decided here — see ``POST .../review`` — except that
    resubmitting a fixed ``REJECTED`` package moves it back to
    ``PENDING_REVIEW`` automatically.
    """
    files, warnings = service.write_metadata_package_raw(
        principal,
        model_id=model_id,
        files=[(f.filename, f.content) for f in payload.files],
    )
    return _raw_response(model_id, files, warnings)


@router.post("/models/{model_id}/review", response_model=RegisterModelResponse)
async def review_model_metadata_package(
    model_id: str,
    payload: ReviewMetadataPackageRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterModelResponse:
    """An UPLOAD_REVIEWER's approve/reject decision on a PENDING_REVIEW model.

    Gated on the platform-wide ``upload_reviewer`` role, not ownership — the
    human-review step (workflow steps e/f) that replaces
    ``write_metadata_package_raw``'s old self-approve behavior. Self-review
    is allowed here: the caller may hold ``upload_reviewer`` and also be the
    model's uploader.
    """
    resource = await service.review_metadata_package(
        principal,
        model_id=model_id,
        approve=payload.approve,
        reason=payload.reason,
    )
    return _model_response(resource)


@router.post("/models/{model_id}/image", response_model=RegisterModelResponse)
async def submit_model_container_image(
    model_id: str,
    payload: SubmitContainerImageRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterModelResponse:
    """Submit (or resubmit) a built Dockerfile/image for IMAGE_CHECK review.

    Ownership-gated (workflow steps h/l) — the design doc names no gating
    role for submission itself, only for the review action
    (``POST .../image-review``). Requires the model's metadata registration
    to already be ``APPROVED``. Resubmitting after ``IMAGE_REJECTED`` uses
    this same endpoint and auto-transitions back to ``PENDING_IMAGE_CHECK``;
    there is no separate "resubmit" endpoint.
    """
    resource = service.submit_container_image(
        principal,
        model_id=model_id,
        container=Container(
            kind=payload.kind,
            file=payload.file,
            image_name=payload.image_name,
            registry=payload.registry,
        ),
    )
    return _model_response(resource)


@router.post("/models/{model_id}/image-review", response_model=RegisterModelResponse)
async def review_model_container_image(
    model_id: str,
    payload: ReviewContainerImageRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterModelResponse:
    """An IMAGE_CHECK holder's approve/reject decision on a
    PENDING_IMAGE_CHECK model's Dockerfile/image.

    Gated on the platform-wide ``image_checker`` role, not ownership —
    mirrors ``POST .../review``'s pattern (workflow steps i-k). Self-review
    is allowed here: the caller may hold ``image_checker`` and also be the
    model's uploader.
    """
    resource = await service.review_container_image(
        principal,
        model_id=model_id,
        approve=payload.approve,
        reason=payload.reason,
    )
    return _model_response(resource)


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
    run = await service.create_run(
        principal,
        model_id=model_id,
        input_resource_ids=payload.input_resource_ids,
        entrypoint_index=payload.entrypoint_index,
        arguments=payload.arguments,
        triggered_by=principal.subject,
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
    principal: AuthenticatedPrincipalDep,
    status: RunStatus | None = Query(
        default=None, description="Optional filter — only include runs with this status."
    ),
) -> ModelRunDetailsResponse:
    """Fetch the calling user's runs for a model, with hydrated I/O resources.

    Populates the run history on the model detail page in a single call.

    Scoped to the caller: this returns only runs the requesting user triggered,
    filtered in the query rather than after hydration. It previously required no
    authentication and returned *every* user's runs for the model, which —
    paired with the run controls the detail page renders — exposed other
    people's run ids, output downloads, and cancel actions to anonymous
    visitors.

    Runs arrive newest-first from the registry; the order is not re-derived here.
    """
    assert_model_visible(service.get_model(model_id), principal)

    summary = service.get_model_run_details(
        model_id=model_id,
        status=status,
        triggered_by=principal.subject,
    )

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
