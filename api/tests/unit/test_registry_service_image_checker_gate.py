"""Unit tests for AuthorizationService.assert_image_checker (MISM-291).

Covers the platform#image_checker gate: checks `platform:main#image_checker`
before allowing a Dockerfile/image-review action. Mirrors
`test_registry_service_reviewer_gate.py`'s pattern for `assert_upload_reviewer`.

Note: these tests previously targeted RegistryService._assert_image_checker.
Phase 4 migrated them to AuthorizationService.assert_image_checker directly,
since that is now the home of all OpenFGA gate logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.authorization_service import AuthorizationService


def _principal(subject: str = "frank") -> AuthenticatedPrincipal:
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


async def test_assert_image_checker_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    authz = _make_authz(client)

    await authz.assert_image_checker(_principal("frank"))

    client.check.assert_awaited_once_with(
        user="user:frank", relation="image_checker", object_="platform:main"
    )


async def test_assert_image_checker_denied_when_check_fails() -> None:
    client = _client(allowed=False)
    authz = _make_authz(client)

    with pytest.raises(APIError) as excinfo:
        await authz.assert_image_checker(_principal("frank"))

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_image_checker_allowed_without_openfga_client() -> None:
    authz = _make_authz(None)

    # No client configured — check is skipped entirely (permissive).
    await authz.assert_image_checker(_principal("frank"))


async def test_assert_image_checker_local_issuer_bypasses_check() -> None:
    # Even a client that would deny the check must never be consulted.
    client = _client(allowed=False)
    authz = _make_authz(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    await authz.assert_image_checker(local_principal)

    client.check.assert_not_awaited()


async def test_assert_image_checker_allows_self_review() -> None:
    """Self-review is explicitly allowed for image_checker (decided 2026-08-21,
    as its own per-role decision, not carried over from `upload_reviewer`'s
    precedent): the gate only checks the role, never compares principal.subject
    against resource.owner."""
    client = _client(allowed=True)
    authz = _make_authz(client)

    # The uploader and the image checker are the same person; the gate doesn't care.
    await authz.assert_image_checker(_principal("dana"))

    client.check.assert_awaited_once_with(
        user="user:dana", relation="image_checker", object_="platform:main"
    )
