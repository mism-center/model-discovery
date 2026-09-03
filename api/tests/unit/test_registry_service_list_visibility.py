"""Unit tests for RegistryService.list_models / list_datasets visibility filtering
(MISM-291 Phase 5 Option A).

list_models and list_datasets now accept a ``principal`` parameter and apply a
string-equality visibility filter (approved OR owner), moving this gate from
the router layer into the service layer.  Tests verify:
  * Anonymous caller (``principal=None``) sees only APPROVED resources.
  * Authenticated caller sees APPROVED resources + their own non-approved ones.
  * Authenticated caller does NOT see another user's non-approved resources.
  * A resource with an empty ``owner`` field is owned by nobody.
  * The ``registration_status`` pre-filter on ``list_models`` composes correctly
    with the visibility filter.
  * ``list_datasets`` mirrors ``list_models`` behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.resource import Resource

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.services.registry_service import RegistryService

_APPROVED = ResourceRegistrationStatus.APPROVED
_PENDING = ResourceRegistrationStatus.PENDING_REVIEW
_DRAFT = ResourceRegistrationStatus.DRAFT


def _principal(subject: str = "alice") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _resource(
    *,
    resource_id: str,
    resource_type: ResourceType = ResourceType.MODEL,
    owner: str = "alice",
    registration_status: ResourceRegistrationStatus = _APPROVED,
) -> Resource:
    return Resource(
        id=resource_id,
        name=f"Resource {resource_id}",
        resource_type=resource_type,
        location_uri=f"irods:///{resource_type.value}s/{resource_id}",
        execution_type=ExecutionType.PYTHON,
        execution_ref="",
        description="",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=registration_status,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_service() -> RegistryService:
    return RegistryService(
        registry=MagicMock(),
        session=MagicMock(),
        openfga_client=None,
    )


# ── list_models — anonymous caller ────────────────────────────────────────────


def test_list_models_anonymous_sees_only_approved() -> None:
    approved = _resource(resource_id="m-1", registration_status=_APPROVED)
    pending = _resource(resource_id="m-2", registration_status=_PENDING)

    with patch(
        "mismapi.services.registry_service.find_resources", return_value=[approved, pending]
    ):
        result = _make_service().list_models(principal=None)

    assert [r.id for r in result] == ["m-1"]


def test_list_models_anonymous_sees_all_approved() -> None:
    resources = [
        _resource(resource_id="m-1", registration_status=_APPROVED),
        _resource(resource_id="m-2", registration_status=_APPROVED),
        _resource(resource_id="m-3", registration_status=_DRAFT, owner="alice"),
    ]

    with patch("mismapi.services.registry_service.find_resources", return_value=resources):
        result = _make_service().list_models(principal=None)

    assert [r.id for r in result] == ["m-1", "m-2"]


# ── list_models — authenticated caller ────────────────────────────────────────


def test_list_models_authenticated_sees_approved_and_own_unapproved() -> None:
    alice_approved = _resource(resource_id="m-1", owner="alice", registration_status=_APPROVED)
    alice_pending = _resource(resource_id="m-2", owner="alice", registration_status=_PENDING)
    bob_pending = _resource(resource_id="m-3", owner="bob", registration_status=_PENDING)

    with patch(
        "mismapi.services.registry_service.find_resources",
        return_value=[alice_approved, alice_pending, bob_pending],
    ):
        result = _make_service().list_models(principal=_principal("alice"))

    assert [r.id for r in result] == ["m-1", "m-2"]


def test_list_models_caller_does_not_see_others_unapproved() -> None:
    bob_pending = _resource(resource_id="m-1", owner="bob", registration_status=_PENDING)

    with patch("mismapi.services.registry_service.find_resources", return_value=[bob_pending]):
        result = _make_service().list_models(principal=_principal("alice"))

    assert result == []


def test_list_models_empty_owner_visible_to_nobody() -> None:
    """A resource with no owner must not be accessible by any principal."""
    no_owner = _resource(resource_id="m-1", owner="", registration_status=_PENDING)

    with patch("mismapi.services.registry_service.find_resources", return_value=[no_owner]):
        result = _make_service().list_models(principal=_principal("alice"))

    assert result == []


def test_list_models_registration_status_prefilter_composes_with_visibility() -> None:
    """registration_status narrowing and visibility filter must compose correctly."""
    approved = _resource(resource_id="m-1", registration_status=_APPROVED)
    pending_alice = _resource(resource_id="m-2", owner="alice", registration_status=_PENDING)

    with patch(
        "mismapi.services.registry_service.find_resources",
        return_value=[approved, pending_alice],
    ):
        # Only ask for pending_review — approved is pre-filtered out, then
        # alice's pending survives the visibility check.
        result = _make_service().list_models(
            principal=_principal("alice"),
            registration_status="pending_review",
        )

    assert [r.id for r in result] == ["m-2"]


# ── list_datasets — mirrors list_models logic ─────────────────────────────────


def test_list_datasets_anonymous_sees_only_approved() -> None:
    approved = _resource(
        resource_id="d-1",
        resource_type=ResourceType.DATASET,
        registration_status=_APPROVED,
    )
    pending = _resource(
        resource_id="d-2",
        resource_type=ResourceType.DATASET,
        registration_status=_PENDING,
    )

    with patch(
        "mismapi.services.registry_service.find_resources", return_value=[approved, pending]
    ):
        result = _make_service().list_datasets(principal=None)

    assert [r.id for r in result] == ["d-1"]


def test_list_datasets_authenticated_sees_approved_and_own_unapproved() -> None:
    alice_approved = _resource(
        resource_id="d-1",
        resource_type=ResourceType.DATASET,
        owner="alice",
        registration_status=_APPROVED,
    )
    alice_pending = _resource(
        resource_id="d-2",
        resource_type=ResourceType.DATASET,
        owner="alice",
        registration_status=_PENDING,
    )
    bob_pending = _resource(
        resource_id="d-3",
        resource_type=ResourceType.DATASET,
        owner="bob",
        registration_status=_PENDING,
    )

    with patch(
        "mismapi.services.registry_service.find_resources",
        return_value=[alice_approved, alice_pending, bob_pending],
    ):
        result = _make_service().list_datasets(principal=_principal("alice"))

    assert [r.id for r in result] == ["d-1", "d-2"]


def test_list_datasets_caller_does_not_see_others_unapproved() -> None:
    bob_pending = _resource(
        resource_id="d-1",
        resource_type=ResourceType.DATASET,
        owner="bob",
        registration_status=_PENDING,
    )

    with patch("mismapi.services.registry_service.find_resources", return_value=[bob_pending]):
        result = _make_service().list_datasets(principal=_principal("alice"))

    assert result == []
