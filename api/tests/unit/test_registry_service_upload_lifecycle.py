"""Unit tests for `RegistryService.mark_upload_complete`.

The interesting behavior is that ``post-finish`` reconciles ``location_uri``
to the canonical iRODS upload directory so the download/listing endpoints can
always locate freshly-uploaded files even when the user supplied a different
``location_uri`` (or none) at create time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from mism_registry.enums import ExecutionType, ResourceStatus, ResourceType
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService


def _principal(subject: str = "user-1") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_service(initial: Resource) -> RegistryService:
    registry = InMemoryRegistry()
    registry.register_resource(initial)
    # The service commits the SQLAlchemy session after each mutation; we don't
    # care what it does here since the in-memory registry persists on its own.
    session = MagicMock()
    return RegistryService(registry=registry, session=session)


def _make_model(
    *,
    resource_id: str = "m-1",
    owner: str = "user-1",
    location_uri: str = "irods:///models/m-1",
) -> Resource:
    return Resource(
        id=resource_id,
        name="Example Model",
        resource_type=ResourceType.MODEL,
        location_uri=location_uri,
        execution_type=ExecutionType.PYTHON,
        execution_ref="",
        description="",
        version="0.1.0",
        status=ResourceStatus.ACTIVE,
        owner=owner,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def test_mark_upload_complete_reconciles_location_uri_to_upload_dir() -> None:
    """The whole point of the reconciliation fix.

    The user can create a model with any (allowed) ``location_uri`` — even an
    empty one — but tus always writes to ``models/{id}/files/``. After the
    upload finishes the resource's URI must point at that directory so
    ``GET /resources/{id}/files`` and ``GET /resources/{id}/download`` find
    the uploaded artifacts.
    """
    service = _make_service(_make_model(location_uri="irods:///some/old/place"))

    updated = service.mark_upload_complete(_principal(), resource_id="m-1")

    assert updated.location_uri == "irods:///models/m-1/files"
    assert updated.metadata["upload_status"] == "UPLOAD_COMPLETE"


def test_mark_upload_complete_reconciles_even_when_location_uri_was_empty() -> None:
    """Empty location_uri at create time is the recommended upload-first flow."""
    service = _make_service(_make_model(location_uri=""))

    updated = service.mark_upload_complete(_principal(), resource_id="m-1")

    assert updated.location_uri == "irods:///models/m-1/files"


def test_mark_upload_complete_is_idempotent() -> None:
    """A second invocation should be a no-op equivalent to the first."""
    service = _make_service(_make_model())

    first = service.mark_upload_complete(_principal(), resource_id="m-1")
    second = service.mark_upload_complete(_principal(), resource_id="m-1")

    assert first.location_uri == second.location_uri == "irods:///models/m-1/files"
    assert second.metadata["upload_status"] == "UPLOAD_COMPLETE"


def test_mark_upload_complete_rejects_other_owners() -> None:
    """Ownership is enforced — a different principal sees a 403."""
    service = _make_service(_make_model(owner="user-1"))

    with pytest.raises(APIError) as exc:
        service.mark_upload_complete(_principal("user-2"), resource_id="m-1")

    assert exc.value.status_code == 403
    assert exc.value.code == "not_authorized"


def test_mark_upload_complete_preserves_unrelated_metadata() -> None:
    """Reconciliation must not clobber existing metadata entries."""
    resource = _make_model()
    resource.metadata = {"checksum": "abc123", "source": "biomodels"}
    service = _make_service(resource)

    updated = service.mark_upload_complete(_principal(), resource_id="m-1")

    assert updated.metadata["checksum"] == "abc123"
    assert updated.metadata["source"] == "biomodels"
    assert updated.metadata["upload_status"] == "UPLOAD_COMPLETE"
