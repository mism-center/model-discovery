"""Integration tests for ``GET /api/auth/capabilities`` (MISM-291)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from mismapi.core.deps import _get_registry_service
from mismapi.services.registry_service import RegistryService
from tests.conftest import (
    build_test_app,
    minimal_oidc_settings,
    override_anonymous,
    override_principal,
)


def _service_returning(capabilities: dict[str, bool]) -> MagicMock:
    service = MagicMock(spec=RegistryService)
    service.get_platform_capabilities.return_value = capabilities
    return service


def test_capabilities_returns_grants_from_the_service() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        override_principal(app)
        app.dependency_overrides[_get_registry_service] = lambda: _service_returning(
            {
                "uploader": True,
                "upload_reviewer": False,
                "image_checker": False,
                "executor": True,
            }
        )
        with TestClient(app) as client:
            response = client.get("/api/auth/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "uploader": True,
        "upload_reviewer": False,
        "image_checker": False,
        "executor": True,
    }


def test_capabilities_requires_authentication() -> None:
    settings = minimal_oidc_settings()
    with build_test_app(settings) as app:
        override_anonymous(app)
        with TestClient(app) as client:
            response = client.get("/api/auth/capabilities")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_missing"
