"""Unit tests for AuthorizationService.assert_upload_reviewer (MISM-291).

Covers the platform#upload_reviewer gate: checks `platform:main#upload_reviewer`
before allowing a metadata-review action. Mirrors
`test_registry_service_uploader_gate.py`'s pattern for `assert_uploader`.

Note: these tests previously targeted RegistryService._assert_upload_reviewer.
Phase 4 migrated them to AuthorizationService.assert_upload_reviewer directly,
since that is now the home of all OpenFGA gate logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.authorization_service import AuthorizationService


def _principal(subject: str = "erin") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_authz(openfga_client: OpenFGAClient | None) -> AuthorizationService:
    return AuthorizationService(client=openfga_client)


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


async def test_assert_upload_reviewer_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    authz = _make_authz(client)

    await authz.assert_upload_reviewer(_principal("erin"))

    client.check.assert_awaited_once_with(
        user="user:erin", relation="upload_reviewer", object_="platform:main"
    )


async def test_assert_upload_reviewer_denied_when_check_fails() -> None:
    client = _client(allowed=False)
    authz = _make_authz(client)

    with pytest.raises(APIError) as excinfo:
        await authz.assert_upload_reviewer(_principal("erin"))

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_upload_reviewer_allowed_without_openfga_client() -> None:
    authz = _make_authz(None)

    # No client configured — check is skipped entirely (permissive).
    await authz.assert_upload_reviewer(_principal("erin"))


async def test_assert_upload_reviewer_local_issuer_bypasses_check() -> None:
    # Even a client that would deny the check must never be consulted.
    client = _client(allowed=False)
    authz = _make_authz(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    await authz.assert_upload_reviewer(local_principal)

    client.check.assert_not_awaited()


async def test_assert_upload_reviewer_allows_self_review() -> None:
    """Self-review is explicitly allowed (decided 2026-08-21): the gate only checks
    the role, never compares principal.subject against resource.owner."""
    client = _client(allowed=True)
    authz = _make_authz(client)

    # The uploader and the reviewer are the same person; the gate doesn't care.
    await authz.assert_upload_reviewer(_principal("dana"))

    client.check.assert_awaited_once_with(
        user="user:dana", relation="upload_reviewer", object_="platform:main"
    )
