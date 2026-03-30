import logging

from fastapi import APIRouter, Request
from mism_registry.search import FieldFilter, SearchQuery

from mismapi.schemas.search import (
    AggBucketDTO,
    AggResultDTO,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_resources(request: Request, body: SearchRequest) -> SearchResponse:
    """Full-text search across models and datasets with filters and aggregations."""
    service: RegistryService = request.app.state.registry_service

    query = SearchQuery(
        text=body.query,
        filters=tuple(
            FieldFilter(field=f.field, op=f.op, value=f.value) for f in body.filters
        ),
        agg_fields=tuple(body.aggs),
        sort_field=body.sort.field,
        sort_order=body.sort.order,
        limit=body.limit,
        offset=body.offset,
    )

    result = service.search(query)

    items = [
        SearchResultItem(
            id=r.id,
            name=r.name,
            resource_type=r.resource_type.value,
            location_uri=r.location_uri,
            description=r.description,
            version=r.version,
            status=r.status.value,
            owner=r.owner,
            execution_type=r.execution_type.value if r.execution_type else None,
            organisms=r.organisms,
            domains=r.domains,
            modeling_scales=r.modeling_scales,
            format_tags=r.format_tags,
            created_at=r.created_at,
            updated_at=r.updated_at,
            score=result.scores[i] if result.scores else None,
        )
        for i, r in enumerate(result.resources)
    ]

    aggs = {
        field_name: AggResultDTO(
            buckets=[AggBucketDTO(key=b.key, count=b.count) for b in buckets]
        )
        for field_name, buckets in result.aggs.items()
    }

    return SearchResponse(total=result.total, results=items, aggs=aggs)
