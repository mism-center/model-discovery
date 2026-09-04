"""Unit tests for RegistryService.assert_can_view_model (MISM-291, Phase 2).

Covers the three resolution paths:
  * Anonymous caller (principal is None) — registration_status check only.
  * Authenticated caller with FGA client — OpenFGA can_view on model:{id}.
  * Authenticated caller without FGA client (local dev / unconfigured) —
    string-equality fallback (approved OR owner match).
"""

from __future__ import annotations

from datetime import UTC, datetime
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


def _principal(subject: str = "alice", *, issuer: str = "test") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer=issuer,
        audience="mism-api",
        scopes=set(),
    )


def _resource(
    *,
    resource_id: str = "m-1",
    owner: str = "alice",
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.APPROVED,
) -> Resource:
    return Resource(
        id=resource_id,
        name="Example Model",
        resource_type=ResourceType.MODEL,
        location_uri=f"irods:///models/{resource_id}",
        execution_type=ExecutionType.PYTHON,
        execution_ref="",
        description="",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=registration_status,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_service(openfga_client: OpenFGAClient | None) -> RegistryService:
    return RegistryService(
        registry=InMemoryRegistry(),
        session=MagicMock(),
        openfga_client=openfga_client,
    )


# Short aliases so parametrize and resource() calls don't blow the 100-char limit.
_APPROVED = ResourceRegistrationStatus.APPROVED
_PENDING = ResourceRegistrationStatus.PENDING_REVIEW


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


# ── Anonymous caller (principal is None) ─────────────────────────────────────


async def test_anonymous_can_view_approved_model() -> None:
    service = _make_service(None)

    # Must not raise — approved models are public.
    await service.assert_can_view_model(
        None, resource=_resource(registration_status=ResourceRegistrationStatus.APPROVED)
    )


@pytest.mark.parametrize(
    "registration_status",
    [
        ResourceRegistrationStatus.DRAFT,
        ResourceRegistrationStatus.ANNOTATING,
        ResourceRegistrationStatus.PENDING_REVIEW,
        ResourceRegistrationStatus.REJECTED,
    ],
)
async def test_anonymous_cannot_view_unapproved_model(
    registration_status: ResourceRegistrationStatus,
) -> None:
    service = _make_service(None)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_model(
            None, resource=_resource(registration_status=registration_status)
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


# ── Authenticated caller with FGA client ─────────────────────────────────────


async def test_fga_client_allowed_passes() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service.assert_can_view_model(_principal("alice"), resource=_resource())

    client.check.assert_awaited_once_with(
        user="user:alice", relation="can_view", object_="model:m-1"
    )


async def test_fga_client_denied_raises_404() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_model(
            _principal("bob"),
            resource=_resource(owner="alice", registration_status=_PENDING),
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


# ── Authenticated caller without FGA client (string-equality fallback) ────────


async def test_no_fga_client_approved_visible_to_anyone() -> None:
    """An approved model is public — any authenticated caller can view it."""
    service = _make_service(None)

    await service.assert_can_view_model(
        _principal("bob"),
        resource=_resource(owner="alice", registration_status=_APPROVED),
    )


async def test_no_fga_client_unapproved_visible_to_owner() -> None:
    """An unapproved model is visible to its owner (string-equality match)."""
    service = _make_service(None)

    await service.assert_can_view_model(
        _principal("alice"),
        resource=_resource(owner="alice", registration_status=_PENDING),
    )


async def test_no_fga_client_unapproved_not_visible_to_non_owner() -> None:
    """An unapproved model is invisible to anyone who isn't its owner."""
    service = _make_service(None)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_model(
            _principal("bob"),
            resource=_resource(owner="alice", registration_status=_PENDING),
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


# ── Local issuer (disable_auth dev mode) ─────────────────────────────────────


async def test_local_issuer_bypasses_fga_uses_string_equality_fallback() -> None:
    """Local issuer skips the FGA check (returns None from _openfga_client_for).

    Falls back to string equality: unapproved + non-owner → 404.
    The FGA client is configured but must not be called.
    """
    client = _client(allowed=True)  # would allow — but must not be called
    service = _make_service(client)
    local_principal = _principal("bob", issuer="local")

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_model(
            local_principal,
            resource=_resource(owner="alice", registration_status=_PENDING),
        )

    client.check.assert_not_awaited()
    assert excinfo.value.status_code == 404


async def test_local_issuer_owner_can_view_without_fga() -> None:
    """Local issuer + owner match → allowed without FGA."""
    client = _client(allowed=False)  # would deny — but must not be called
    service = _make_service(client)
    local_principal = _principal("alice", issuer="local")

    await service.assert_can_view_model(
        local_principal,
        resource=_resource(owner="alice", registration_status=_PENDING),
    )

    client.check.assert_not_awaited()
