"""Unit tests for RegistryService.review_metadata_package (MISM-291).

Covers the model-owner approve/reject action: ownership gate via
`_assert_model_owner` (OpenFGA ``owner`` relation on ``model:{id}``),
delegation to `mism_registry.set_registration_status` (state machine +
reviewer-identity stamping), and error mapping
(InvalidStateTransitionError -> 400).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

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
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "dana") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    client.write_tuple = AsyncMock()
    return client


def _make_service(
    openfga_client: OpenFGAClient | None,
    *,
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.PENDING_REVIEW,
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
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    session = MagicMock()
    return RegistryService(registry=registry, session=session, openfga_client=openfga_client)


# ── Ownership gate (OpenFGA path) ─────────────────────────────────────────


async def test_review_denied_when_openfga_check_fails() -> None:
    service = _make_service(_client(allowed=False))

    with pytest.raises(APIError) as excinfo:
        await service.review_metadata_package(_principal("dana"), model_id="m-1", approve=True)

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_review_openfga_check_uses_owner_relation_on_model_object() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service.review_metadata_package(_principal("dana"), model_id="m-1", approve=True)

    client.check.assert_awaited_once_with(user="user:dana", relation="owner", object_="model:m-1")


# ── Ownership gate (Postgres fallback — no OpenFGA client) ────────────────


async def test_review_denied_when_no_client_and_not_owner() -> None:
    # No OpenFGA client → falls back to Postgres string equality.
    service = _make_service(None, owner="dana")

    with pytest.raises(APIError) as excinfo:
        await service.review_metadata_package(_principal("erin"), model_id="m-1", approve=True)

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_review_denied_when_no_client_and_model_not_found() -> None:
    # No client + nonexistent model → get_resource_and_assert_ownership collapses to 403.
    service = _make_service(None)

    with pytest.raises(APIError) as excinfo:
        await service.review_metadata_package(
            _principal("dana"), model_id="does-not-exist", approve=True
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_review_local_issuer_bypasses_all_auth_checks() -> None:
    # issuer=="local" → OpenFGA skipped; get_resource_and_assert_ownership also
    # skips its ownership check for local principals (dev/disable_auth mode).
    # Both auth layers are fully bypassed — the action succeeds regardless of
    # whether the principal owns the model.
    client = _client(allowed=False)  # would deny if consulted, but it won't be
    service = _make_service(client, owner="dana")
    local_principal = AuthenticatedPrincipal(
        subject="erin", issuer="local", audience="local", scopes=set()
    )

    resource = await service.review_metadata_package(local_principal, model_id="m-1", approve=True)

    client.check.assert_not_awaited()
    assert resource.registration_status == ResourceRegistrationStatus.APPROVED


# ── Approve ──────────────────────────────────────────────────────────────


async def test_approve_transitions_to_approved_and_stamps_reviewer() -> None:
    service = _make_service(_client(allowed=True))

    resource = await service.review_metadata_package(
        _principal("dana"), model_id="m-1", approve=True
    )

    assert resource.registration_status == ResourceRegistrationStatus.APPROVED
    assert resource.metadata_reviewed_by == "dana"
    assert resource.metadata_reviewed_at is not None
    assert resource.metadata_rejection_reason == ""


# ── Reject ───────────────────────────────────────────────────────────────


async def test_reject_transitions_to_rejected_and_records_reason() -> None:
    service = _make_service(_client(allowed=True))

    resource = await service.review_metadata_package(
        _principal("dana"), model_id="m-1", approve=False, reason="Missing license info."
    )

    assert resource.registration_status == ResourceRegistrationStatus.REJECTED
    assert resource.metadata_reviewed_by == "dana"
    assert resource.metadata_rejection_reason == "Missing license info."


# ── Error mapping ────────────────────────────────────────────────────────


async def test_review_illegal_transition_raises_400() -> None:
    # APPROVED is a terminal state — no transition out of it is legal.
    service = _make_service(
        _client(allowed=True), registration_status=ResourceRegistrationStatus.APPROVED
    )

    with pytest.raises(APIError) as excinfo:
        await service.review_metadata_package(_principal("dana"), model_id="m-1", approve=True)

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "invalid_state_transition"


async def test_review_illegal_transition_does_not_commit() -> None:
    service = _make_service(
        _client(allowed=True), registration_status=ResourceRegistrationStatus.APPROVED
    )
    session = cast(MagicMock, service._session)

    with pytest.raises(APIError):
        await service.review_metadata_package(_principal("dana"), model_id="m-1", approve=True)

    session.commit.assert_not_called()
    session.rollback.assert_called_once()


# ── OpenFGA viewer-tuple writes (Phase 1a) ───────────────────────────────


async def test_approve_writes_viewer_wildcard_tuple() -> None:
    """Approving a model writes viewer@user:* so anonymous can_view checks succeed."""
    client = _client(allowed=True)
    service = _make_service(client)

    await service.review_metadata_package(_principal("erin"), model_id="m-1", approve=True)

    client.write_tuple.assert_awaited_once_with(
        user="user:*", relation="viewer", object_="model:m-1"
    )


async def test_reject_does_not_write_viewer_tuple() -> None:
    """Rejecting must not write a viewer tuple — the model stays private."""
    client = _client(allowed=True)
    service = _make_service(client)

    await service.review_metadata_package(
        _principal("erin"), model_id="m-1", approve=False, reason="Needs fixes."
    )

    client.write_tuple.assert_not_awaited()


async def test_approve_rolls_back_when_viewer_tuple_write_fails() -> None:
    """A FGA failure on approve rolls back the DB so the two stores stay in sync."""
    client = _client(allowed=True)
    client.write_tuple = AsyncMock(
        side_effect=APIError(status_code=502, code="openfga_write_failed", detail="boom")
    )
    service = _make_service(client)
    session = cast(MagicMock, service._session)

    with pytest.raises(APIError) as excinfo:
        await service.review_metadata_package(_principal("erin"), model_id="m-1", approve=True)

    assert excinfo.value.code == "openfga_write_failed"
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


async def test_approve_without_openfga_client_skips_viewer_tuple() -> None:
    """No client configured — state still transitions, no crash, no tuple write."""
    # No FGA client → _assert_model_owner falls back to ownership string-equality,
    # so the principal must match the resource owner.
    service = _make_service(None, owner="dana")
    session = cast(MagicMock, service._session)

    resource = await service.review_metadata_package(
        _principal("dana"), model_id="m-1", approve=True
    )

    assert resource.registration_status == ResourceRegistrationStatus.APPROVED
    session.commit.assert_called_once()


async def test_approve_local_issuer_skips_viewer_tuple() -> None:
    """disable_auth dev mode skips all OpenFGA, including the viewer tuple write."""
    client = _client(allowed=True)
    service = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="erin", issuer="local", audience="local", scopes=set()
    )

    resource = await service.review_metadata_package(local_principal, model_id="m-1", approve=True)

    assert resource.registration_status == ResourceRegistrationStatus.APPROVED
    client.write_tuple.assert_not_awaited()
