import logging

from fastapi import APIRouter, Depends, Query

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.dependencies.registry import get_registry_service
from mismapi.schemas.registry import (
    RegisterDatasetRequest,
    RegisterDatasetResponse,
    UpdateDatasetRequest,
)
from mismapi.schemas.search import ModelListItem, ModelListResponse
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/datasets", response_model=RegisterDatasetResponse, status_code=201)
async def create_dataset(
    payload: RegisterDatasetRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
    service: RegistryService = Depends(get_registry_service),
) -> RegisterDatasetResponse:

    resource = service.create_dataset(
        principal,
        name=payload.name,
        location_uri=payload.location_uri,
        description=payload.description,
        version=payload.version,
        owner=payload.owner,
        format_tags=payload.format_tags,
        metadata=payload.metadata,
    )

    return RegisterDatasetResponse(
        id=resource.id,
        name=resource.name,
        resource_type=resource.resource_type.value,
        location_uri=resource.location_uri,
        description=resource.description,
        version=resource.version,
        status=resource.status.value,
        owner=resource.owner,
        format_tags=list(resource.format_tags),
        created_at=resource.created_at,
    )


@router.put("/datasets/{dataset_id}", response_model=RegisterDatasetResponse)
async def update_dataset(
    dataset_id: str,
    payload: UpdateDatasetRequest,
    principal: AuthenticatedPrincipal = Depends(require_principal),
    service: RegistryService = Depends(get_registry_service),
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
        metadata=payload.metadata,
    )

    return RegisterDatasetResponse(
        id=resource.id,
        name=resource.name,
        resource_type=resource.resource_type.value,
        location_uri=resource.location_uri,
        description=resource.description,
        version=resource.version,
        status=resource.status.value,
        owner=resource.owner,
        format_tags=list(resource.format_tags),
        created_at=resource.created_at,
    )


@router.get("/datasets", response_model=ModelListResponse)
async def list_datasets(
    name: str | None = Query(default=None, description="Substring match on dataset name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Modeling scales (any must match)"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: RegistryService = Depends(get_registry_service),
) -> ModelListResponse:

    resources = service.list_datasets(
        name_contains=name,
        owner=owner,
        tags=tags,
        organisms=organisms,
        scales=scales,
    )

    total = len(resources)
    page = resources[offset : offset + limit]

    results = [
        ModelListItem(
            id=r.id,
            name=r.name,
            resource_type=r.resource_type.value,
            location_uri=r.location_uri,
            execution_type=r.execution_type.value if r.execution_type else None,
            version=r.version,
            status=r.status.value,
            owner=r.owner,
            description=r.description,
            created_at=r.created_at,
        )
        for r in page
    ]

    return ModelListResponse(total=total, results=results)
