"""Unit tests for RegistryService.assert_can_view_run / assert_can_cancel_run
(MISM-291, Phase 3).

Both methods delegate to the private ``_assert_run_relation`` helper with their
respective relation names (``can_view`` / ``can_cancel``).  Tests verify:
  * The correct OpenFGA relation and object are used.
  * Denial raises 404 (not 403) — id-oracle-avoidance convention.
  * No FGA client → string-equality fallback on ``run.triggered_by``.
  * Local issuer → _openfga_client_for returns None → string-equality fallback.
  * Empty ``triggered_by`` is owned by nobody (historical rows predating
    attribution stay invisible).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.enums import RunStatus
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.run import Run

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


def _run(*, run_id: str = "run-1", triggered_by: str = "alice") -> Run:
    return Run(
        id=run_id,
        model_id="m-1",
        model_version="0.1.0",
        status=RunStatus.COMPLETED,
        input_resource_ids=[],
        output_resource_ids=[],
        parameters={},
        triggered_by=triggered_by,
        notes="",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_service(openfga_client: OpenFGAClient | None) -> RegistryService:
    return RegistryService(
        registry=InMemoryRegistry(),
        session=MagicMock(),
        openfga_client=openfga_client,
    )


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    return client


# ── assert_can_view_run — FGA client present ──────────────────────────────────


async def test_can_view_run_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service.assert_can_view_run(_principal("alice"), run=_run())

    client.check.assert_awaited_once_with(
        user="user:alice", relation="can_view", object_="run:run-1"
    )


async def test_can_view_run_denied_raises_404() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_run(_principal("bob"), run=_run(triggered_by="alice"))

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


# ── assert_can_cancel_run — FGA client present ────────────────────────────────


async def test_can_cancel_run_allowed_when_check_passes() -> None:
    client = _client(allowed=True)
    service = _make_service(client)

    await service.assert_can_cancel_run(_principal("alice"), run=_run())

    client.check.assert_awaited_once_with(
        user="user:alice", relation="can_cancel", object_="run:run-1"
    )


async def test_can_cancel_run_denied_raises_404() -> None:
    client = _client(allowed=False)
    service = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_cancel_run(_principal("bob"), run=_run(triggered_by="alice"))

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


# ── No FGA client — string-equality fallback ─────────────────────────────────


async def test_no_fga_client_can_view_when_triggered_by_matches() -> None:
    service = _make_service(None)

    await service.assert_can_view_run(_principal("alice"), run=_run(triggered_by="alice"))


async def test_no_fga_client_cannot_view_when_triggered_by_mismatches() -> None:
    service = _make_service(None)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_run(_principal("bob"), run=_run(triggered_by="alice"))

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


async def test_no_fga_client_empty_triggered_by_is_owned_by_nobody() -> None:
    """A run with no triggered_by must not be accessible by anyone."""
    service = _make_service(None)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_run(_principal("alice"), run=_run(triggered_by=""))

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


async def test_no_fga_client_can_cancel_when_triggered_by_matches() -> None:
    service = _make_service(None)

    await service.assert_can_cancel_run(_principal("alice"), run=_run(triggered_by="alice"))


async def test_no_fga_client_cannot_cancel_when_triggered_by_mismatches() -> None:
    service = _make_service(None)

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_cancel_run(_principal("bob"), run=_run(triggered_by="alice"))

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


# ── Local issuer — skips FGA, uses string-equality fallback ──────────────────


async def test_local_issuer_bypasses_fga_and_uses_triggered_by_match() -> None:
    client = _client(allowed=False)  # would deny — must not be called
    service = _make_service(client)
    local_principal = _principal("alice", issuer="local")

    await service.assert_can_view_run(local_principal, run=_run(triggered_by="alice"))

    client.check.assert_not_awaited()


async def test_local_issuer_still_denies_on_triggered_by_mismatch() -> None:
    client = _client(allowed=True)  # would allow — must not be called
    service = _make_service(client)
    local_principal = _principal("bob", issuer="local")

    with pytest.raises(APIError) as excinfo:
        await service.assert_can_view_run(local_principal, run=_run(triggered_by="alice"))

    client.check.assert_not_awaited()
    assert excinfo.value.status_code == 404
