"""Unit tests for RegistryService.create_run's can_execute gate (MISM-291).

Covers the end-to-end wiring: ``create_run`` calls
``AuthorizationService.assert_can_execute`` on the per-model
``model:{model_id}#can_execute`` relation before creating a run, and writes
the run-owner tuple via ``grant_run_owner`` after.

Direct tests for ``AuthorizationService.assert_can_execute`` in isolation live
in ``test_authorization_service.py``.
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
from mismapi.services.authorization_service import AuthorizationService
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "alice") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _approved_model(
    *,
    resource_id: str = "m-1",
    owner: str = "alice",
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
        registration_status=ResourceRegistrationStatus.APPROVED,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_service(
    openfga_client: OpenFGAClient | None, *, model: Resource | None = None
) -> tuple[RegistryService, MagicMock]:
    registry = InMemoryRegistry()
    if model is not None:
        registry.register_resource(model)
    session = MagicMock()
    service = RegistryService(
        registry=registry, session=session, authz=AuthorizationService(client=openfga_client)
    )
    return service, session


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    client.write_tuple = AsyncMock()
    return client


# ── create_run wiring ────────────────────────────────────────────────


async def test_create_run_allowed_when_can_execute_check_passes() -> None:
    client = _client(allowed=True)
    service, session = _make_service(client, model=_approved_model())

    run = await service.create_run(_principal("alice"), model_id="m-1")

    assert run.model_id == "m-1"
    client.check.assert_awaited_once_with(
        user="user:alice", relation="can_execute", object_="model:m-1"
    )
    session.commit.assert_called_once()


async def test_create_run_denied_when_can_execute_check_fails() -> None:
    client = _client(allowed=False)
    service, session = _make_service(client, model=_approved_model())

    with pytest.raises(APIError) as excinfo:
        await service.create_run(_principal("bob"), model_id="m-1")

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"
    # Denial happens before prepare_run/commit — nothing should have been created.
    session.commit.assert_not_called()


async def test_create_run_allowed_without_openfga_client() -> None:
    service, session = _make_service(None, model=_approved_model())

    run = await service.create_run(_principal("alice"), model_id="m-1")

    assert run.model_id == "m-1"
    session.commit.assert_called_once()


async def test_create_run_local_issuer_bypasses_can_execute_check() -> None:
    client = _client(allowed=False)
    service, _ = _make_service(client, model=_approved_model())
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    run = await service.create_run(local_principal, model_id="m-1")

    assert run.model_id == "m-1"
    client.check.assert_not_awaited()


async def test_create_run_missing_model_returns_404_before_authz_check() -> None:
    """A bad model_id must still 404, not 403 — the existence check (and its
    404 mapping) runs before `_assert_can_execute`, matching this method's
    pre-existing behavior for a nonexistent model_id."""
    client = _client(allowed=False)
    service, _ = _make_service(client, model=None)

    with pytest.raises(APIError) as excinfo:
        await service.create_run(_principal("alice"), model_id="missing")

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"
    client.check.assert_not_awaited()


# ── OpenFGA run-owner tuple writes (Phase 1b) ────────────────────────────


async def test_create_run_writes_owner_tuple() -> None:
    """create_run grants owner on run:{id} so OpenFGA can_view / can_cancel resolve."""
    client = _client(allowed=True)
    service, _ = _make_service(client, model=_approved_model())

    run = await service.create_run(_principal("alice"), model_id="m-1")

    client.write_tuple.assert_awaited_once_with(
        user="user:alice",
        relation="owner",
        object_=f"run:{run.id}",
    )


async def test_create_run_rolls_back_when_owner_tuple_write_fails() -> None:
    """A FGA failure on run creation rolls back the DB to keep the two stores in sync."""
    client = _client(allowed=True)
    client.write_tuple = AsyncMock(
        side_effect=APIError(status_code=502, code="openfga_write_failed", detail="boom")
    )
    service, session = _make_service(client, model=_approved_model())

    with pytest.raises(APIError) as excinfo:
        await service.create_run(_principal("alice"), model_id="m-1")

    assert excinfo.value.code == "openfga_write_failed"
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


async def test_create_run_without_openfga_client_skips_owner_tuple() -> None:
    """No client configured — run is created and committed with no tuple write."""
    service, session = _make_service(None, model=_approved_model())

    run = await service.create_run(_principal("alice"), model_id="m-1")

    assert run.model_id == "m-1"
    session.commit.assert_called_once()


async def test_create_run_local_issuer_skips_owner_tuple() -> None:
    """disable_auth dev mode skips all OpenFGA, including the run-owner tuple write."""
    client = _client(allowed=True)
    service, _ = _make_service(client, model=_approved_model())
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    run = await service.create_run(local_principal, model_id="m-1")

    assert run.model_id == "m-1"
    client.write_tuple.assert_not_awaited()
