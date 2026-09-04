"""Unit tests for RegistryService's platform#upload_reviewer gate (MISM-291).

Covers Checkpoint 3-A: `_assert_upload_reviewer` checks `platform:main#upload_reviewer`
before allowing a metadata-review action. Exercised directly (not through a public
service method) because no public caller wires it in yet — Checkpoint 3-B adds the
review endpoint that calls it for real. Mirrors `test_registry_service_uploader_gate.py`'s
pattern for `_assert_uploader`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.in_memory import InMemoryRegistry

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "erin") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_service(openfga_client: OpenFGAClient | None) -> RegistryService:
    registry = InMemoryRegistry()
    session = MagicMock()
    return RegistryService(registry=registry, session=session, openfga_client=openfga_client)


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


async def test_assert_upload_reviewer_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service._assert_upload_reviewer(_principal("erin"))

    client.check.assert_awaited_once_with(
        user="user:erin", relation="upload_reviewer", object_="platform:main"
    )


async def test_assert_upload_reviewer_denied_when_check_fails() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service._assert_upload_reviewer(_principal("erin"))

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_upload_reviewer_allowed_without_openfga_client() -> None:
    service = _make_service(None)

    # No client configured (e.g. RegistryService constructed directly in tests) —
    # the check is skipped entirely, matching `_assert_uploader`'s behavior.
    await service._assert_upload_reviewer(_principal("erin"))


async def test_assert_upload_reviewer_local_issuer_bypasses_check() -> None:
    # Even a client that would deny the check must never be consulted.
    client = _client(allowed=False)
    service = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    await service._assert_upload_reviewer(local_principal)

    client.check.assert_not_awaited()


async def test_assert_upload_reviewer_allows_self_review() -> None:
    """Self-review is explicitly allowed (decided 2026-08-21): the gate only checks
    the role, never compares principal.subject against resource.owner."""
    client = _client(allowed=True)
    service = _make_service(client)

    # The uploader and the reviewer are the same person; the gate doesn't care.
    await service._assert_upload_reviewer(_principal("dana"))

    client.check.assert_awaited_once_with(
        user="user:dana", relation="upload_reviewer", object_="platform:main"
    )
