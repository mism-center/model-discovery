from fastapi import APIRouter, Query

from mismapi.core.deps import SearchClientDep
from mismapi.schemas.search import SearchResponse

router = APIRouter()


@router.get("/models", response_model=SearchResponse)
async def search_models(
    client: SearchClientDep,
    q: str = Query(min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    return await client.search(query=q, limit=limit, offset=offset)
