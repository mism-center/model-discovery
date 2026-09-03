"""Unit tests for RegistryService's create_run input-resource visibility gate
(MISM-291, Checkpoint 5-B).

Covers `_assert_input_resource_visible`: `create_run` previously passed
`input_resource_ids` straight to `prepare_run` with no visibility check, so a
caller could name someone else's private dataset as a run input and have its
contents surfaced back via the run's mounted filesystem/outputs
(`Docs/OpenFGA/MISM-OpenFGA-Auth-Model.md`, goal 1, checklist item 8). This is
an interim string-equality check (approved OR owner match), not a real
OpenFGA `can_view` check — see the docstring on
`_assert_input_resource_visible` for why.

The model itself is always caller-owned and OpenFGA-unconfigured (`client=None`)
in these tests so `_assert_can_execute` (Checkpoint 5-A) never interferes —
these tests isolate the *input-resource* gate specifically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

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
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "alice") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _model(*, resource_id: str = "m-1", owner: str = "alice") -> Resource:
    return Resource(
        id=resource_id,
        name="Example Model",
        resource_type=ResourceType.MODEL,
        location_uri=f"irods:///models/{resource_id}",
        execution_type=ExecutionType.PYTHON,
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=ResourceRegistrationStatus.APPROVED,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _dataset(
    *,
    resource_id: str = "ds-1",
    owner: str = "alice",
    registration_status: ResourceRegistrationStatus = ResourceRegistrationStatus.APPROVED,
) -> Resource:
    return Resource(
        id=resource_id,
        name="Example Dataset",
        resource_type=ResourceType.DATASET,
        location_uri=f"irods:///datasets/{resource_id}",
        version="0.1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        registration_status=registration_status,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _make_service(*resources: Resource) -> tuple[RegistryService, MagicMock]:
    registry = InMemoryRegistry()
    for resource in resources:
        registry.register_resource(resource)
    session = MagicMock()
    # No OpenFGA client: _assert_can_execute is a no-op, isolating this gate.
    service = RegistryService(registry=registry, session=session, openfga_client=None)
    return service, session


async def test_create_run_allows_public_input_resource() -> None:
    service, session = _make_service(
        _model(owner="alice"),
        _dataset(owner="bob", registration_status=ResourceRegistrationStatus.APPROVED),
    )

    run = await service.create_run(_principal("alice"), model_id="m-1", input_resource_ids=["ds-1"])

    assert run.input_resource_ids == ["ds-1"]
    session.commit.assert_called_once()


async def test_create_run_allows_input_resource_owned_by_caller_even_if_private() -> None:
    service, session = _make_service(
        _model(owner="alice"),
        _dataset(owner="alice", registration_status=ResourceRegistrationStatus.DRAFT),
    )

    run = await service.create_run(_principal("alice"), model_id="m-1", input_resource_ids=["ds-1"])

    assert run.input_resource_ids == ["ds-1"]
    session.commit.assert_called_once()


async def test_create_run_denies_someone_elses_private_input_resource() -> None:
    service, session = _make_service(
        _model(owner="alice"),
        _dataset(owner="bob", registration_status=ResourceRegistrationStatus.DRAFT),
    )

    with pytest.raises(APIError) as excinfo:
        await service.create_run(_principal("alice"), model_id="m-1", input_resource_ids=["ds-1"])

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"
    # Denial happens before prepare_run/commit — nothing should have been created.
    session.commit.assert_not_called()


async def test_create_run_missing_input_resource_returns_404() -> None:
    service, session = _make_service(_model(owner="alice"))

    with pytest.raises(APIError) as excinfo:
        await service.create_run(
            _principal("alice"), model_id="m-1", input_resource_ids=["missing"]
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"
    session.commit.assert_not_called()


async def test_create_run_checks_every_input_resource_not_just_the_first() -> None:
    """A visible first input must not short-circuit the check for a later,
    invisible one."""
    service, session = _make_service(
        _model(owner="alice"),
        _dataset(
            resource_id="ds-1", owner="alice", registration_status=ResourceRegistrationStatus.DRAFT
        ),
        _dataset(
            resource_id="ds-2", owner="bob", registration_status=ResourceRegistrationStatus.DRAFT
        ),
    )

    with pytest.raises(APIError) as excinfo:
        await service.create_run(
            _principal("alice"), model_id="m-1", input_resource_ids=["ds-1", "ds-2"]
        )

    assert excinfo.value.status_code == 404
    session.commit.assert_not_called()


async def test_create_run_with_no_input_resources_skips_the_gate_entirely() -> None:
    service, session = _make_service(_model(owner="alice"))

    run = await service.create_run(_principal("alice"), model_id="m-1")

    assert run.input_resource_ids == []
    session.commit.assert_called_once()
