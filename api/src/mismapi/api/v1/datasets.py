import logging

from fastapi import APIRouter, Query
from mism_registry.resource import Resource

from mismapi.api.v1._authz import model_visible_to
from mismapi.auth.base import AuthenticatedPrincipalDep, OptionalPrincipalDep
from mismapi.core.deps import RegistryServiceDep
from mismapi.schemas.registry import (
    RegisterDatasetRequest,
    RegisterDatasetResponse,
    UpdateDatasetRequest,
    author_from_dto,
    author_to_dto,
    io_spec_to_dto,
    pub_from_dto,
    pub_to_dto,
)
from mismapi.schemas.search import ModelListItem, ModelListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _dataset_list_item(r: Resource) -> ModelListItem:
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


def _dataset_response(r: Resource) -> RegisterDatasetResponse:
    return RegisterDatasetResponse(
        id=r.id,
        name=r.name,
        resource_type=r.resource_type.value,
        location_uri=r.location_uri,
        description=r.description,
        version=r.version,
        status=r.version_status.value,
        owner=r.owner,
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


@router.post("/datasets", response_model=RegisterDatasetResponse, status_code=201)
async def create_dataset(
    payload: RegisterDatasetRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterDatasetResponse:
    resource = await service.create_dataset(
        principal,
        name=payload.name,
        location_uri=payload.location_uri,
        description=payload.description,
        version=payload.version,
        owner=payload.owner,
        format_tags=payload.format_tags,
        digest_sha256=payload.digest_sha256,
        size_bytes=payload.size_bytes,
        external_ids=payload.external_ids,
        license=payload.license,
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

    return _dataset_response(resource)


@router.put("/datasets/{dataset_id}", response_model=RegisterDatasetResponse)
async def update_dataset(
    dataset_id: str,
    payload: UpdateDatasetRequest,
    service: RegistryServiceDep,
    principal: AuthenticatedPrincipalDep,
) -> RegisterDatasetResponse:
    resource = service.update_dataset(
        principal,
        dataset_id=dataset_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        owner=payload.owner,
        location_uri=payload.location_uri,
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

    return _dataset_response(resource)


@router.get("/datasets", response_model=ModelListResponse)
async def list_datasets(
    service: RegistryServiceDep,
    principal: OptionalPrincipalDep,
    name: str | None = Query(default=None, description="Substring match on dataset name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Model scales (any must match)"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ModelListResponse:
    resources = service.list_datasets(
        name_contains=name,
        owner=owner,
        tags=tags,
        organisms=organisms,
        scales=scales,
    )

    # Same visibility rule as GET /models: approved datasets are public,
    # anything still in draft / annotating / pending_review / rejected is
    # visible only to its owner. Filtering before pagination keeps `total`
    # and the page contents consistent — counting hidden rows would leak
    # their existence through the count alone.
    visible = [r for r in resources if model_visible_to(r, principal)]

    total = len(visible)
    page = visible[offset : offset + limit]

    return ModelListResponse(total=total, results=[_dataset_list_item(r) for r in page])
