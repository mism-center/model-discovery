"""Unit tests for RegistryService.create_model's OpenFGA tuple-writing (MISM-291).

Covers the one FUTURE hook wired in Checkpoint B: on model creation, grant
`owner` to the creating principal and write the boilerplate `platform` tuple
so `model#can_execute`'s tupleToUserset can resolve later.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mism_registry.enums import ExecutionType
from mism_registry.in_memory import InMemoryRegistry

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "alice") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_service(openfga_client: OpenFGAClient | None) -> tuple[RegistryService, MagicMock]:
    registry = InMemoryRegistry()
    session = MagicMock()
    service = RegistryService(registry=registry, session=session, openfga_client=openfga_client)
    return service, session


async def test_create_model_writes_owner_and_platform_tuples() -> None:
    client = MagicMock(spec=OpenFGAClient)
    client.write_tuple = AsyncMock()
    service, session = _make_service(client)

    resource = await service.create_model(
        _principal("alice"),
        name="Test Model",
        location_uri="irods:///models/m-1",
        execution_type=ExecutionType.PYTHON,
    )

    assert client.write_tuple.await_count == 2
    calls = client.write_tuple.await_args_list
    assert calls[0].kwargs == {
        "user": "user:alice",
        "relation": "owner",
        "object_": f"model:{resource.id}",
    }
    assert calls[1].kwargs == {
        "user": "platform:main",
        "relation": "platform",
        "object_": f"model:{resource.id}",
    }
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


async def test_create_model_without_openfga_client_is_a_no_op() -> None:
    service, session = _make_service(None)

    resource = await service.create_model(
        _principal("alice"),
        name="Test Model",
        location_uri="irods:///models/m-2",
        execution_type=ExecutionType.PYTHON,
    )

    assert resource.name == "Test Model"
    session.commit.assert_called_once()


async def test_create_model_local_issuer_skips_tuple_writes() -> None:
    """disable_auth dev mode (issuer == "local") skips OpenFGA entirely —
    not just the uploader check, but the tuple writes too, since local dev
    commonly runs without an OpenFGA instance at all."""
    client = MagicMock(spec=OpenFGAClient)
    client.write_tuple = AsyncMock()
    service, session = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    resource = await service.create_model(
        local_principal,
        name="Test Model",
        location_uri="irods:///models/m-5",
        execution_type=ExecutionType.PYTHON,
    )

    assert resource.name == "Test Model"
    client.write_tuple.assert_not_awaited()
    session.commit.assert_called_once()


async def test_create_model_rolls_back_when_openfga_write_fails() -> None:
    client = MagicMock(spec=OpenFGAClient)
    client.write_tuple = AsyncMock(
        side_effect=APIError(status_code=502, code="openfga_write_failed", detail="boom")
    )
    service, session = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.create_model(
            _principal("alice"),
            name="Test Model",
            location_uri="irods:///models/m-3",
            execution_type=ExecutionType.PYTHON,
        )

    assert excinfo.value.code == "openfga_write_failed"
    session.commit.assert_not_called()
    session.rollback.assert_called_once()
