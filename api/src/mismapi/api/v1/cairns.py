import logging
from collections import defaultdict

from fastapi import APIRouter
from mism_registry.enums import ResourceRegistrationStatus
from mism_registry.resource import Resource

from mismapi.api.v1._authz import model_visible_to
from mismapi.auth.base import OptionalPrincipalDep
from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.deps import CairnsClientDep, RegistryServiceDep
from mismapi.core.errors import APIError
from mismapi.schemas.cairns import (
    MISM_SOURCE,
    CairnsEvidenceCardDTO,
    CairnsRecommendRequest,
    CairnsRecommendResponse,
)
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cairns/recommend", response_model=CairnsRecommendResponse)
async def cairns_recommend(
    body: CairnsRecommendRequest,
    client: CairnsClientDep,
    registry: RegistryServiceDep,
    principal: OptionalPrincipalDep,
) -> CairnsRecommendResponse:
    """Ask CAIRNS for computational tools and models matching a question.

    Each card's `mism_model_id` links it to this registry, under the same
    visibility rule as the model pages. A MISM card names a registry model
    directly; any other card links to an import of the same record.
    """
    response = await client.recommend(body)
    cards = response.evidence
    models = _visible_models(
        {c.metadata.identifier for c in cards if c.source == MISM_SOURCE}, registry, principal
    )
    imports = _visible_imports([c for c in cards if c.source != MISM_SOURCE], registry, principal)

    def registry_model_id(card: CairnsEvidenceCardDTO) -> str | None:
        identifier = card.metadata.identifier
        if card.source == MISM_SOURCE:
            return identifier if identifier in models else None
        return imports.get((card.source, identifier))

    evidence = [
        card.model_copy(update={"mism_model_id": registry_model_id(card)}) for card in cards
    ]
    return response.model_copy(update={"evidence": evidence})


def _visible_models(
    model_ids: set[str],
    registry: RegistryService,
    principal: AuthenticatedPrincipal | None,
) -> set[str]:
    """The models among `model_ids` this registry holds that the caller may see."""
    visible: set[str] = set()
    try:
        for model_id in model_ids:
            try:
                model = registry.get_model(model_id)
            except APIError as exc:
                if exc.status_code == 404:
                    continue
                raise
            if model_visible_to(model, principal):
                visible.add(model_id)
    except Exception:
        # Linking into the registry is a bonus. A broken registry must not cost
        # the caller an answer CAIRNS already spent tens of seconds producing.
        logger.exception("registry_lookup_failed model_ids=%d", len(model_ids))
        return set()
    return visible


def _visible_imports(
    cards: list[CairnsEvidenceCardDTO],
    registry: RegistryService,
    principal: AuthenticatedPrincipal | None,
) -> dict[tuple[str, str], str]:
    """(source, identifier) -> id of this registry's import of that record the caller may see.

    An import records its upstream as `source_repository` / `source_identifier`,
    which for a CAIRNS card are its `source` and `metadata.identifier`.
    """
    wanted: dict[str, set[str]] = defaultdict(set)
    for card in cards:
        if card.metadata.identifier:
            wanted[card.source].add(card.metadata.identifier)

    imports: list[Resource] = []
    try:
        for source, identifiers in wanted.items():
            imports += registry.find_by_source(repository=source, identifiers=list(identifiers))
    except Exception:
        logger.exception("registry_crossref_failed sources=%d", len(wanted))
        return {}

    visible = [r for r in imports if model_visible_to(r, principal)]
    # Approved sorts last so it wins the dict: uq_resources_source lets a caller
    # see both an approved copy and their own unapproved import of one model.
    visible.sort(key=lambda r: r.registration_status == ResourceRegistrationStatus.APPROVED)
    return {(r.source_repository, r.source_identifier): r.id for r in visible}
