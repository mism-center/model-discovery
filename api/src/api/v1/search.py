from fastapi import APIRouter, Query, Request

from src.clients.search_client import SearchServiceClient
from src.schemas.search import SearchResponse

router = APIRouter()


@router.get("/models", response_model=SearchResponse)
async def search_models(
    request: Request,
    q: str = Query(min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    client: SearchServiceClient = request.app.state.search_client
    return await client.search(query=q, limit=limit, offset=offset)
