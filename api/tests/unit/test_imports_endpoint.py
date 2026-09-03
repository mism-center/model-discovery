"""Tests for POST /api/v1/imports/biomodels.

The import itself is covered in test_biomodels_import.py; these assert the
route's wiring, its auth gate, and the JSON the client actually receives.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from mism_registry.enums import ResourceRegistrationStatus

from mismapi.clients.biomodels_client import BioModelsClient
from mismapi.clients.execution_client import ExecutionClient
from mismapi.core.deps import _get_biomodels_client, _get_execution_client, _get_registry_service
from mismapi.core.errors import APIError
from mismapi.services import biomodels_import
from mismapi.services.registry_service import RegistryService
from tests.conftest import (
    build_test_client,
    make_settings,
    override_anonymous,
    override_principal,
)

_MODEL_ID = "BIOMD0000000732"


def _configure(app: FastAPI) -> None:
    override_principal(app)
    app.dependency_overrides[_get_registry_service] = lambda: AsyncMock(spec=RegistryService)
    app.dependency_overrides[_get_biomodels_client] = lambda: AsyncMock(spec=BioModelsClient)
    app.dependency_overrides[_get_execution_client] = lambda: AsyncMock(spec=ExecutionClient)


def _stub_import(
    monkeypatch: pytest.MonkeyPatch, *, result: Any = None, error: APIError | None = None
) -> None:
    async def fake(*args: Any, **kwargs: Any) -> Any:
        if error is not None:
            raise error
        return result

    monkeypatch.setattr("mismapi.api.v1.imports.import_biomodels_model", fake)


def _imported_model(model_id: str = "model-1") -> Any:
    resource = MagicMock()
    resource.id = model_id
    resource.registration_status = ResourceRegistrationStatus.DRAFT
    resource.source_identifier = _MODEL_ID
    return biomodels_import.ImportedModel(
        resource=resource,
        files_extracted=2,
        size_bytes=1234,
        annotation_started=True,
    )


def test_successful_import_returns_201_with_the_new_model_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_import(monkeypatch, result=_imported_model())

    with build_test_client(make_settings(), configure=_configure) as (_, client):
        response = client.post("/api/v1/imports/biomodels", json={"model_id": _MODEL_ID})

    assert response.status_code == 201
    assert response.json() == {
        "model_id": "model-1",
        "registration_status": "draft",
        "source_identifier": _MODEL_ID,
        "files_extracted": 2,
        "size_bytes": 1234,
        "annotation_started": True,
    }


def test_duplicate_import_surfaces_the_existing_model_id_in_error_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The UI links to the existing model, so the id must be machine-readable."""
    _stub_import(
        monkeypatch,
        error=APIError(
            status_code=409,
            code="biomodels_already_imported",
            detail=f"{_MODEL_ID} is already in the registry as model model-1.",
            meta={"model_id": "model-1", "registration_status": "APPROVED"},
        ),
    )

    with build_test_client(make_settings(), configure=_configure) as (_, client):
        response = client.post("/api/v1/imports/biomodels", json={"model_id": _MODEL_ID})

    assert response.status_code == 409
    assert response.json()["error"]["meta"]["model_id"] == "model-1"


def test_errors_without_meta_keep_the_original_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_import(
        monkeypatch,
        error=APIError(
            status_code=400, code="biomodels_invalid_model_id", detail="'nope' is not a model id."
        ),
    )

    with build_test_client(make_settings(), configure=_configure) as (_, client):
        response = client.post("/api/v1/imports/biomodels", json={"model_id": "nope"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "biomodels_invalid_model_id", "detail": "'nope' is not a model id."}
    }


def test_import_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    """The import fires an annotation job, so it spends the deployment's LLM budget."""
    called = False

    async def fake(*args: Any, **kwargs: Any) -> Any:
        nonlocal called
        called = True
        return _imported_model()

    monkeypatch.setattr("mismapi.api.v1.imports.import_biomodels_model", fake)

    def configure(app: FastAPI) -> None:
        override_anonymous(app)

    with build_test_client(make_settings(), configure=configure) as (_, client):
        response = client.post("/api/v1/imports/biomodels", json={"model_id": _MODEL_ID})

    assert response.status_code == 401
    assert called is False


def test_missing_model_id_is_a_request_validation_error() -> None:
    with build_test_client(make_settings(), configure=_configure) as (_, client):
        response = client.post("/api/v1/imports/biomodels", json={})

    assert response.status_code == 400
