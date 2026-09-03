"""Unit tests for RegistryService._assert_model_owner (MISM-291).

Covers the per-model OpenFGA ownership gate: checks ``owner`` on
``model:{model_id}`` (not a platform-wide object), falls back to Postgres
string equality when no OpenFGA client is available, and respects the same
``issuer == "local"`` bypass as every other ``_assert_*`` gate.

Mirrors ``test_registry_service_image_checker_gate.py``'s pattern, adapted
for the per-resource (not platform-wide) object and the Postgres fallback.
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


def _principal(subject: str = "dana", issuer: str = "test") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer=issuer, audience="mism-api", scopes=set())


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


def _make_service(
    openfga_client: OpenFGAClient | None,
    *,
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
            registration_status=ResourceRegistrationStatus.PENDING_REVIEW,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    session = MagicMock()
    return RegistryService(registry=registry, session=session, openfga_client=openfga_client)


async def test_assert_model_owner_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service._assert_model_owner(_principal("dana"), model_id="m-1")

    client.check.assert_awaited_once_with(user="user:dana", relation="owner", object_="model:m-1")


async def test_assert_model_owner_denied_when_check_fails() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service._assert_model_owner(_principal("dana"), model_id="m-1")

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_model_owner_uses_per_model_object_not_platform() -> None:
    """The check must target ``model:{model_id}``, not ``platform:main``."""
    client = _client(allowed=True)
    service = _make_service(client)

    await service._assert_model_owner(_principal("dana"), model_id="some-other-id")

    client.check.assert_awaited_once_with(
        user="user:dana", relation="owner", object_="model:some-other-id"
    )


async def test_assert_model_owner_no_openfga_client_falls_back_to_postgres() -> None:
    # No client → falls back to get_resource_and_assert_ownership (Postgres).
    # The model's owner matches → no error raised.
    service = _make_service(None, owner="dana")

    await service._assert_model_owner(_principal("dana"), model_id="m-1")


async def test_assert_model_owner_no_openfga_client_non_owner_denied() -> None:
    # Postgres fallback: owner mismatch → 403.
    service = _make_service(None, owner="dana")

    with pytest.raises(APIError) as excinfo:
        await service._assert_model_owner(_principal("erin"), model_id="m-1")

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_model_owner_local_issuer_bypasses_openfga() -> None:
    # issuer=="local" → _openfga_client_for returns None → Postgres fallback.
    # OpenFGA is never consulted even if a client is configured.
    client = _client(allowed=False)  # would deny if consulted
    service = _make_service(client, owner="dana")
    local_principal = _principal("dana", issuer="local")

    # Owner matches in Postgres → no error despite client returning False.
    await service._assert_model_owner(local_principal, model_id="m-1")

    client.check.assert_not_awaited()
