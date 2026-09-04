"""Unit tests for RegistryService's platform#uploader gate on creation (MISM-291).

Covers Checkpoint C: `create_model`/`create_dataset` both check
`platform:main#uploader` via `_assert_uploader` before doing anything else.
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


def _principal(subject: str = "dana") -> AuthenticatedPrincipal:
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


def _client(allowed: bool) -> MagicMock:
    client = MagicMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=allowed)
    client.write_tuple = AsyncMock()
    return client


# ── create_model ─────────────────────────────────────────────────────


async def test_create_model_allowed_when_uploader_check_passes() -> None:
    client = _client(allowed=True)
    service, _ = _make_service(client)

    resource = await service.create_model(
        _principal("dana"),
        name="Test Model",
        location_uri="irods:///models/m-1",
        execution_type=ExecutionType.PYTHON,
    )

    assert resource.name == "Test Model"
    client.check.assert_awaited_once_with(
        user="user:dana", relation="uploader", object_="platform:main"
    )


async def test_create_model_denied_when_uploader_check_fails() -> None:
    client = _client(allowed=False)
    service, session = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.create_model(
            _principal("dana"),
            name="Test Model",
            location_uri="irods:///models/m-2",
            execution_type=ExecutionType.PYTHON,
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"
    # Nothing should have been attempted — denial happens before register_model.
    client.write_tuple.assert_not_awaited()
    session.commit.assert_not_called()


async def test_create_model_allowed_without_openfga_client() -> None:
    service, session = _make_service(None)

    resource = await service.create_model(
        _principal("dana"),
        name="Test Model",
        location_uri="irods:///models/m-3",
        execution_type=ExecutionType.PYTHON,
    )

    assert resource.name == "Test Model"
    session.commit.assert_called_once()


# ── create_dataset ───────────────────────────────────────────────────


async def test_create_dataset_allowed_when_uploader_check_passes() -> None:
    client = _client(allowed=True)
    service, _ = _make_service(client)

    resource = await service.create_dataset(
        _principal("dana"),
        name="Test Dataset",
        location_uri="s3://bucket/d-1.csv",
    )

    assert resource.name == "Test Dataset"
    client.check.assert_awaited_once_with(
        user="user:dana", relation="uploader", object_="platform:main"
    )


async def test_create_dataset_denied_when_uploader_check_fails() -> None:
    client = _client(allowed=False)
    service, session = _make_service(client)

    with pytest.raises(APIError) as excinfo:
        await service.create_dataset(
            _principal("dana"),
            name="Test Dataset",
            location_uri="s3://bucket/d-2.csv",
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "not_authorized"
    session.commit.assert_not_called()


async def test_create_dataset_allowed_without_openfga_client() -> None:
    service, session = _make_service(None)

    resource = await service.create_dataset(
        _principal("dana"),
        name="Test Dataset",
        location_uri="s3://bucket/d-3.csv",
    )

    assert resource.name == "Test Dataset"
    session.commit.assert_called_once()


# ── issuer == "local" bypass (disable_auth dev mode) ────────────────


async def test_create_model_local_issuer_bypasses_uploader_check() -> None:
    # Even a client that would deny the check must never be consulted.
    client = _client(allowed=False)
    service, _ = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    resource = await service.create_model(
        local_principal,
        name="Test Model",
        location_uri="irods:///models/m-4",
        execution_type=ExecutionType.PYTHON,
    )

    assert resource.name == "Test Model"
    client.check.assert_not_awaited()


async def test_create_dataset_local_issuer_bypasses_uploader_check() -> None:
    client = _client(allowed=False)
    service, _ = _make_service(client)
    local_principal = AuthenticatedPrincipal(
        subject="anonymous", issuer="local", audience="local", scopes=set()
    )

    resource = await service.create_dataset(
        local_principal,
        name="Test Dataset",
        location_uri="s3://bucket/d-4.csv",
    )

    assert resource.name == "Test Dataset"
    client.check.assert_not_awaited()
