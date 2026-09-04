"""Unit tests for RegistryService.review_container_image (MISM-291, Checkpoint 4-D).

Covers the IMAGE_CHECK approve/reject action: role gate via
`_assert_image_checker`, delegation to `mism_registry.set_image_review_status`
(state machine + reviewer-identity stamping), and error mapping
(ResourceNotFoundError -> 404, InvalidStateTransitionError -> 400). Mirrors
`test_registry_service_review.py`'s pattern for `review_metadata_package`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.enums import (
    ExecutionType,
    ImageReviewStatus,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "frank") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


def _make_service(
    openfga_client: OpenFGAClient | None,
    *,
    image_review_status: ImageReviewStatus = ImageReviewStatus.PENDING_IMAGE_CHECK,
    owner: str = "dana",
) -> RegistryService:
    registry = InMemoryRegistry()
    registry.register_resource(
        Resource(
            id="m-1",
            name="Example Model",
            resource_type=ResourceType.MODEL,
            location_uri="irods:///m-1/0.1.0",
            execution_type=ExecutionType.PYTHON,
            version="0.1.0",
            version_status=ResourceVersionStatus.ACTIVE,
            owner=owner,
            registration_status=ResourceRegistrationStatus.APPROVED,
            image_review_status=image_review_status,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    session = MagicMock()
    return RegistryService(registry=registry, session=session, openfga_client=openfga_client)


# ── Role gate ────────────────────────────────────────────────────────────


async def test_review_denied_when_not_an_image_checker() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.review_container_image(_principal("frank"), model_id="m-1", approve=True)

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_review_allows_self_review() -> None:
    """The image checker and the model's owner may be the same person
    (decided 2026-08-21, as its own per-role choice for image_checker)."""
    client = _client(allowed=True)
    service = _make_service(client, owner="frank")

    resource = await service.review_container_image(
        _principal("frank"), model_id="m-1", approve=True
    )

    assert resource.image_review_status == ImageReviewStatus.IMAGE_APPROVED


# ── Approve ──────────────────────────────────────────────────────────────


async def test_approve_transitions_to_image_approved_and_stamps_reviewer() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    resource = await service.review_container_image(
        _principal("frank"), model_id="m-1", approve=True
    )

    assert resource.image_review_status == ImageReviewStatus.IMAGE_APPROVED
    assert resource.image_reviewed_by == "frank"
    assert resource.image_reviewed_at is not None
    assert resource.image_rejection_reason == ""


# ── Reject ───────────────────────────────────────────────────────────────


async def test_reject_transitions_to_image_rejected_and_records_reason() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    resource = await service.review_container_image(
        _principal("frank"), model_id="m-1", approve=False, reason="Image fails to build."
    )

    assert resource.image_review_status == ImageReviewStatus.IMAGE_REJECTED
    assert resource.image_reviewed_by == "frank"
    assert resource.image_rejection_reason == "Image fails to build."


# ── Error mapping ────────────────────────────────────────────────────────


async def test_review_missing_model_raises_404() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.review_container_image(
            _principal("frank"), model_id="does-not-exist", approve=True
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


async def test_review_illegal_transition_raises_400() -> None:
    client = _client(allowed=True)
    # NOT_APPLICABLE (no container submitted yet) has no image-check transition.
    service = _make_service(client, image_review_status=ImageReviewStatus.NOT_APPLICABLE)

    with pytest.raises(APIError) as excinfo:
        await service.review_container_image(_principal("frank"), model_id="m-1", approve=True)

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "invalid_state_transition"


async def test_review_illegal_transition_does_not_commit() -> None:
    client = _client(allowed=True)
    service = _make_service(client, image_review_status=ImageReviewStatus.NOT_APPLICABLE)
    session = cast(MagicMock, service._session)

    with pytest.raises(APIError):
        await service.review_container_image(_principal("frank"), model_id="m-1", approve=True)

    session.commit.assert_not_called()
    session.rollback.assert_called_once()
