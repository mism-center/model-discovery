"""Unit tests for RegistryService.submit_container_image (MISM-291, Checkpoint 4-C).

Covers the ownership-gated submit/resubmit action: ownership gate via
`get_resource_and_assert_ownership` (not `_assert_image_checker` — no gating role
for submission itself, only for the review action), delegation to
`mism_registry.submit_container_image` (registration-must-be-APPROVED + image-review
state machine), and error mapping (RegistryValidationError -> 400 validation_error,
InvalidStateTransitionError -> 400 invalid_state_transition). Mirrors
`test_registry_service_review.py`'s pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

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
from mism_registry.types import Container

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "dana") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _container(image_name: str = "my-model:latest") -> Container:
    return Container(
        kind="docker", file="Dockerfile", image_name=image_name, registry="ghcr.io/mism-center"
    )


def _make_service(
    *,
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.APPROVED,
    image_review_status: ImageReviewStatus = ImageReviewStatus.NOT_APPLICABLE,
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
            registration_status=registration_status,
            image_review_status=image_review_status,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    session = MagicMock()
    return RegistryService(registry=registry, session=session, openfga_client=None)


# ── Ownership gate ───────────────────────────────────────────────────────


def test_submit_denied_when_not_owner() -> None:
    service = _make_service(owner="dana")

    with pytest.raises(APIError) as excinfo:
        service.submit_container_image(
            _principal("mallory"), model_id="m-1", container=_container()
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


def test_submit_missing_model_raises_403_not_authorized() -> None:
    """Missing model is indistinguishable from "not owner" per
    `get_resource_and_assert_ownership`'s existing convention."""
    service = _make_service()

    with pytest.raises(APIError) as excinfo:
        service.submit_container_image(
            _principal("dana"), model_id="does-not-exist", container=_container()
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


# ── Submit ───────────────────────────────────────────────────────────────


def test_submit_transitions_to_pending_image_check() -> None:
    service = _make_service()

    resource = service.submit_container_image(
        _principal("dana"), model_id="m-1", container=_container()
    )

    assert resource.image_review_status == ImageReviewStatus.PENDING_IMAGE_CHECK
    assert resource.containers == [_container()]


def test_submit_requires_registration_approved() -> None:
    service = _make_service(registration_status=ResourceRegistrationStatus.PENDING_REVIEW)

    with pytest.raises(APIError) as excinfo:
        service.submit_container_image(_principal("dana"), model_id="m-1", container=_container())

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "validation_error"


# ── Resubmission / bounceback ───────────────────────────────────────────


def test_resubmit_after_rejection_auto_transitions_to_pending_image_check() -> None:
    """Decided 2026-08-21: resubmitting after IMAGE_REJECTED auto-transitions back
    to PENDING_IMAGE_CHECK -- there is no separate "resubmit" action, matching the
    metadata-review flow's REJECTED -> PENDING_REVIEW bounceback."""
    service = _make_service(image_review_status=ImageReviewStatus.IMAGE_REJECTED)

    resource = service.submit_container_image(
        _principal("dana"), model_id="m-1", container=_container("fixed-image:latest")
    )

    assert resource.image_review_status == ImageReviewStatus.PENDING_IMAGE_CHECK


def test_resubmit_while_already_pending_raises_400() -> None:
    """No re-review mid-flight: a second submission while a review is already
    outstanding is an illegal transition, not a silent replace."""
    service = _make_service(image_review_status=ImageReviewStatus.PENDING_IMAGE_CHECK)

    with pytest.raises(APIError) as excinfo:
        service.submit_container_image(_principal("dana"), model_id="m-1", container=_container())

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "invalid_state_transition"


def test_illegal_transition_does_not_commit() -> None:
    service = _make_service(image_review_status=ImageReviewStatus.PENDING_IMAGE_CHECK)
    session = cast(MagicMock, service._session)

    with pytest.raises(APIError):
        service.submit_container_image(_principal("dana"), model_id="m-1", container=_container())

    session.commit.assert_not_called()
    session.rollback.assert_called_once()
