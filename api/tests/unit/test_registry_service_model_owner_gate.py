"""Unit tests for AuthorizationService.assert_model_owner (MISM-291).

Covers the per-model OpenFGA ownership gate: checks ``owner`` on
``model:{model_id}`` (not a platform-wide object), and respects the
``issuer == "local"`` bypass as every other gate.

When no OpenFGA client is configured the check is permissive (skipped
entirely). Callers that need a Postgres ownership fallback should additionally
call ``RegistryService.get_resource_and_assert_ownership``.

Note: these tests previously targeted RegistryService._assert_model_owner.
Phase 4 migrated them to AuthorizationService.assert_model_owner directly,
since that is now the home of all OpenFGA gate logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.authorization_service import AuthorizationService


def _principal(subject: str = "dana", issuer: str = "test") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer=issuer, audience="mism-api", scopes=set())


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


def _make_authz(openfga_client: OpenFGAClient | None) -> AuthorizationService:
    return AuthorizationService(client=openfga_client)


async def test_assert_model_owner_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    authz = _make_authz(client)

    await authz.assert_model_owner(_principal("dana"), model_id="m-1")

    client.check.assert_awaited_once_with(user="user:dana", relation="owner", object_="model:m-1")


async def test_assert_model_owner_denied_when_check_fails() -> None:
    client = _client(allowed=False)
    authz = _make_authz(client)

    with pytest.raises(APIError) as excinfo:
        await authz.assert_model_owner(_principal("dana"), model_id="m-1")

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_model_owner_uses_per_model_object_not_platform() -> None:
    """The check must target ``model:{model_id}``, not ``platform:main``."""
    client = _client(allowed=True)
    authz = _make_authz(client)

    await authz.assert_model_owner(_principal("dana"), model_id="some-other-id")

    client.check.assert_awaited_once_with(
        user="user:dana", relation="owner", object_="model:some-other-id"
    )


async def test_assert_model_owner_no_openfga_client_is_permissive() -> None:
    # No client → check is skipped entirely; any principal is allowed through.
    # Postgres ownership is enforced separately by get_resource_and_assert_ownership.
    authz = _make_authz(None)

    await authz.assert_model_owner(_principal("erin"), model_id="m-1")


async def test_assert_model_owner_local_issuer_bypasses_openfga() -> None:
    # issuer == "local" → _client_for returns None → check is skipped entirely.
    # OpenFGA is never consulted even if a client is configured.
    client = _client(allowed=False)  # would deny if consulted
    authz = _make_authz(client)
    local_principal = _principal("anonymous", issuer="local")

    await authz.assert_model_owner(local_principal, model_id="m-1")

    client.check.assert_not_awaited()
