import logging

from fastapi import APIRouter

from mismapi.core.deps import CairnsClientDep
from mismapi.schemas.cairns import CairnsRecommendRequest, CairnsRecommendResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cairns/recommend", response_model=CairnsRecommendResponse)
async def cairns_recommend(
    body: CairnsRecommendRequest,
    client: CairnsClientDep,
) -> CairnsRecommendResponse:
    """Ask CAIRNS for computational tools and models matching a question."""
    return await client.recommend(body)
