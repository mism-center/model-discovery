"""Unit tests for RegistryService's platform#image_checker gate (MISM-291).

Covers Checkpoint 4-A: `_assert_image_checker` checks `platform:main#image_checker`
before allowing a Dockerfile/image-review action. Exercised directly (not through a
public service method) because no public caller wires it in yet — Checkpoint 4-D adds
the image-review endpoint that calls it for real. Mirrors
`test_registry_service_uploader_gate.py`'s pattern for `_assert_uploader`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.in_memory import InMemoryRegistry

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "frank") -> AuthenticatedPrincipal:
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


async def test_assert_image_checker_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service._assert_image_checker(_principal("frank"))

    client.check.assert_awaited_once_with(
        user="user:frank", relation="image_checker", object_="platform:main"
    )


async def test_assert_image_checker_denied_when_check_fails() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service._assert_image_checker(_principal("frank"))

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"


async def test_assert_image_checker_allowed_without_openfga_client() -> None:
    service = _make_service(None)

    # No client configured (e.g. RegistryService constructed directly in tests) —
    # the check is skipped entirely, matching `_assert_uploader`'s behavior.
    await service._assert_image_checker(_principal("frank"))


async def test_assert_image_checker_local_issuer_bypasses_check() -> None:
    # Even a client that would deny the check must never be consulted.
    client = _client(allowed=False)
    service = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    await service._assert_image_checker(local_principal)

    client.check.assert_not_awaited()


async def test_assert_image_checker_allows_self_review() -> None:
    """Self-review is explicitly allowed for image_checker (decided 2026-08-21,
    as its own per-role decision, not carried over from `upload_reviewer`'s
    precedent): the gate only checks the role, never compares principal.subject
    against resource.owner."""
    client = _client(allowed=True)
    service = _make_service(client)

    # The uploader and the image checker are the same person; the gate doesn't care.
    await service._assert_image_checker(_principal("dana"))

    client.check.assert_awaited_once_with(
        user="user:dana", relation="image_checker", object_="platform:main"
    )
