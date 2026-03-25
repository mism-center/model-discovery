import logging

from fastapi import APIRouter, Query, Request

from mismapi.schemas.search import ModelListItem, ModelListResponse
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    request: Request,
    name: str | None = Query(default=None, description="Substring match on model name"),
    owner: str | None = Query(default=None, description="Exact match on owner"),
    tags: list[str] | None = Query(default=None, description="Format tags (all must match)"),
    organisms: list[str] | None = Query(default=None, description="Organisms (any must match)"),
    scales: list[str] | None = Query(default=None, description="Modeling scales (any must match)"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ModelListResponse:
    service: RegistryService = request.app.state.registry_service

    resources = service.list_models(
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
