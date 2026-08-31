import logging

from fastapi import APIRouter

from mismapi.core.deps import BioModelsClientDep, CairnsClientDep
from mismapi.schemas.cairns import (
    CairnsEvidenceCardDTO,
    CairnsRecommendRequest,
    CairnsRecommendResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cairns/recommend", response_model=CairnsRecommendResponse)
async def cairns_recommend(
    body: CairnsRecommendRequest,
    client: CairnsClientDep,
    biomodels: BioModelsClientDep,
) -> CairnsRecommendResponse:
    """Ask CAIRNS for computational tools and models matching a question.

    Evidence cards sourced from BioModels carry a `biomodels` block resolved
    from the BioModels repository; it is null when that lookup found nothing.
    """
    response = await client.recommend(body)

    model_ids = {i for card in response.evidence if (i := card.biomodels_model_id)}
    if not model_ids:
        return response

    try:
        records = await biomodels.get_models(sorted(model_ids))
    except Exception:
        # Resolving evidence is a bonus. A broken BioModels must not cost the
        # caller an answer CAIRNS already spent tens of seconds producing.
        logger.exception("biomodels_enrichment_failed model_ids=%d", len(model_ids))
        return response

    logger.info(
        "biomodels_enrichment resolved=%d requested=%d",
        len(records),
        len(model_ids),
    )
    evidence: list[CairnsEvidenceCardDTO] = [
        card.model_copy(update={"biomodels": records.get(card.biomodels_model_id or "")})
        for card in response.evidence
    ]
    return response.model_copy(update={"evidence": evidence})
