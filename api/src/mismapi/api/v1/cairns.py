import logging

from fastapi import APIRouter
from mism_registry.enums import ResourceRegistrationStatus

from mismapi.api.v1._authz import model_visible_to
from mismapi.auth.base import OptionalPrincipalDep
from mismapi.core.deps import BioModelsClientDep, CairnsClientDep, RegistryServiceDep
from mismapi.schemas.cairns import (
    CairnsEvidenceCardDTO,
    CairnsRecommendRequest,
    CairnsRecommendResponse,
)
from mismapi.services.biomodels_import import SOURCE_REPOSITORY

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cairns/recommend", response_model=CairnsRecommendResponse)
async def cairns_recommend(
    body: CairnsRecommendRequest,
    client: CairnsClientDep,
    biomodels: BioModelsClientDep,
    registry: RegistryServiceDep,
    principal: OptionalPrincipalDep,
) -> CairnsRecommendResponse:
    """Ask CAIRNS for computational tools and models matching a question.

    Evidence cards sourced from BioModels carry a `biomodels` block resolved
    from the BioModels repository, and `mism_model_id` when this registry holds
    an import of the same model. Both key off ids parsed from `tool_id`, so
    neither lookup feeds the other and either may fail on its own.
    """
    response = await client.recommend(body)

    model_ids = sorted({i for card in response.evidence if (i := card.biomodels_model_id)})
    if not model_ids:
        return response

    try:
        records = await biomodels.get_models(model_ids)
    except Exception:
        # Resolving evidence is a bonus. A broken BioModels must not cost the
        # caller an answer CAIRNS already spent tens of seconds producing.
        logger.exception("biomodels_enrichment_failed model_ids=%d", len(model_ids))
        records = {}

    try:
        visible = [
            r
            for r in registry.find_by_source(repository=SOURCE_REPOSITORY, identifiers=model_ids)
            if model_visible_to(r, principal)
        ]
    except Exception:
        logger.exception("registry_crossref_failed model_ids=%d", len(model_ids))
        visible = []

    # Approved sorts last so it wins the dict: uq_resources_source lets a caller
    # see both an approved copy and their own unapproved import of one model.
    visible.sort(key=lambda r: r.registration_status == ResourceRegistrationStatus.APPROVED)
    imported = {r.source_identifier: r.id for r in visible}

    logger.info(
        "biomodels_enrichment resolved=%d imported=%d requested=%d",
        len(records),
        len(imported),
        len(model_ids),
    )
    evidence: list[CairnsEvidenceCardDTO] = [
        card.model_copy(
            update={
                "biomodels": records.get(card.biomodels_model_id or ""),
                "mism_model_id": imported.get(card.biomodels_model_id or ""),
            }
        )
        for card in response.evidence
    ]
    return response.model_copy(update={"evidence": evidence})
