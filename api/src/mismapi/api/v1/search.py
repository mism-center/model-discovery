import logging

from fastapi import APIRouter
from mism_registry.search import FieldFilter, SearchQuery

from mismapi.core.deps import RegistryServiceDep
from mismapi.schemas.registry import author_to_dto, io_spec_to_dto, pub_to_dto
from mismapi.schemas.search import (
    AggBucketDTO,
    AggResultDTO,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_resources(
    body: SearchRequest,
    service: RegistryServiceDep,
) -> SearchResponse:
    """Full-text search across models and datasets with filters and aggregations."""

    query = SearchQuery(
        text=body.query,
        filters=tuple(FieldFilter(field=f.field, op=f.op, value=f.value) for f in body.filters),
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
            execution_ref=r.execution_ref,
            io_spec=io_spec_to_dto(r.io_spec) if r.io_spec else None,
            format_tags=list(r.format_tags),
            authors=[author_to_dto(a) for a in r.authors],
            organization=r.organization,
            contact_email=r.contact_email,
            publications=[pub_to_dto(p) for p in r.publications],
            funding=list(r.funding),
            organisms=list(r.organisms),
            domains=list(r.domains),
            modeling_scales=list(r.modeling_scales),
            date_published=r.date_published,
            digest_sha256=r.digest_sha256,
            size_bytes=r.size_bytes,
            external_ids=dict(r.external_ids),
            license=r.license,
            metadata=dict(r.metadata),
            created_at=r.created_at,
            updated_at=r.updated_at,
            score=result.scores[i] if result.scores else None,
        )
        for i, r in enumerate(result.resources)
    ]

    aggs = {
        field_name: AggResultDTO(
            buckets=[AggBucketDTO(key=b.key, count=b.count) for b in buckets if b.key]
        )
        for field_name, buckets in result.aggs.items()
    }

    return SearchResponse(total=result.total, results=items, aggs=aggs)
