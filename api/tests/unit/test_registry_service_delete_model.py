"""Unit tests for RegistryService.delete_model.

Covers the status guard added to block deletion of APPROVED models:
once a model is publicly visible its owner may no longer delete it via
this endpoint.  Pre-approval states (DRAFT, ANNOTATING, PENDING_REVIEW,
ANNOTATION_FAILED, REJECTED) remain deletable by the owner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "alice") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _make_service(resource: Resource) -> RegistryService:
    registry = InMemoryRegistry()
    registry.register_resource(resource)
    session = MagicMock()
    return RegistryService(registry=registry, session=session)


def _make_model(
    *,
    owner: str = "alice",
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.DRAFT,
) -> Resource:
    r = Resource(
        id="m-1",
        name="Test Model",
        resource_type=ResourceType.MODEL,
        location_uri="irods:///models/m-1",
        execution_type=ExecutionType.PYTHON,
        execution_ref="",
        description="",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    r.registration_status = registration_status
    return r


# ── APPROVED guard ────────────────────────────────────────────────


def test_delete_model_raises_409_for_approved_model() -> None:
    service = _make_service(_make_model(registration_status=ResourceRegistrationStatus.APPROVED))

    with pytest.raises(APIError) as excinfo:
        service.delete_model(_principal(), "m-1")

    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "model_already_approved"


def test_delete_model_approved_guard_fires_before_disk_ops() -> None:
    """shutil.rmtree must never be called for an APPROVED model."""
    service = _make_service(_make_model(registration_status=ResourceRegistrationStatus.APPROVED))

    with patch("mismapi.services.registry_service.shutil.rmtree") as mock_rmtree:
        with pytest.raises(APIError):
            service.delete_model(_principal(), "m-1")
        mock_rmtree.assert_not_called()


# ── Pre-approval states are deletable ────────────────────────────


@pytest.mark.parametrize(
    "status",
    [
        ResourceRegistrationStatus.DRAFT,
        ResourceRegistrationStatus.ANNOTATING,
        ResourceRegistrationStatus.ANNOTATION_FAILED,
        ResourceRegistrationStatus.PENDING_REVIEW,
        ResourceRegistrationStatus.REJECTED,
    ],
)
def test_delete_model_allowed_for_pre_approval_status(
    status: ResourceRegistrationStatus, tmp_path: Path
) -> None:
    """The owner can delete a model in any state that precedes APPROVED."""
    resource = _make_model(registration_status=status)
    resource.location_uri = str(tmp_path)
    service = _make_service(resource)

    # Should not raise.
    service.delete_model(_principal(), "m-1")


# ── Ownership is still enforced ───────────────────────────────────


def test_delete_model_rejects_non_owner_even_for_draft() -> None:
    service = _make_service(
        _make_model(owner="alice", registration_status=ResourceRegistrationStatus.DRAFT)
    )

    with pytest.raises(APIError) as excinfo:
        service.delete_model(_principal("bob"), "m-1")

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"
