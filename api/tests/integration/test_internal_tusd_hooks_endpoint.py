"""End-to-end tests for `POST /api/internal/tusd/hooks`.

The internal tusd hook endpoint is deliberately mounted outside the v1
router that enforces `require_principal`, because tusd posts hook events
server-to-server without an `Authorization` header. These tests pin that
contract: the endpoint must process tus hook events even when there is
no Bearer token on the request, and authorization for `pre-create` must
flow entirely through the upload-token in the tus metadata (consulted via
`UploadSessionStoreService`), not through the standard auth chain.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec

from fastapi.testclient import TestClient

from mismapi.core.deps import (
    _get_registry_service,
    _get_settings,
    _get_upload_session_store_service,
)
from mismapi.core.settings import Settings
from mismapi.main import create_app
from mismapi.schemas.auth import UploadTokenClaims
from mismapi.services.registry_service import RegistryService
from mismapi.services.upload_session_store_service import UploadSessionStoreService
from tests.conftest import minimal_oidc_settings


def _build_client(
    *,
    upload_session_store: UploadSessionStoreService,
    registry_service: RegistryService,
    settings: Settings | None = None,
) -> TestClient:
    resolved_settings = settings or minimal_oidc_settings()
    app = create_app(settings=resolved_settings)
    # Override every dependency the internal tusd-hooks route resolves so the
    # test never touches the real container (no Redis / Postgres / OIDC needed).
    app.dependency_overrides[_get_settings] = lambda: resolved_settings
    app.dependency_overrides[_get_upload_session_store_service] = lambda: upload_session_store
    app.dependency_overrides[_get_registry_service] = lambda: registry_service
    return TestClient(app)


def _pre_create_body(
    *,
    resource_id: str,
    upload_token: str = "token-1",
    filename: str = "model.bin",
    size: int = 1024,
) -> dict[str, Any]:
    return {
        "Type": "pre-create",
        "Event": {
            "Upload": {
                "ID": "",
                "Size": size,
                "MetaData": {
                    "resource_id": resource_id,
                    "upload_token": upload_token,
                    "filename": filename,
                },
            }
        },
    }


def test_tusd_hooks_endpoint_processes_pre_create_without_bearer_token() -> None:
    """The hook endpoint must accept and process tus events with no
    `Authorization` header.

    tusd calls this endpoint server-to-server and never sends a Bearer token;
    authorization for `pre-create` is established by the `upload_token` in the
    tus metadata (which the upload session store consumes), not by the
    standard auth chain. This test exercises the full FastAPI route — if the
    endpoint were ever moved under the v1 router (or otherwise gained a
    `require_principal` dependency), this test would fail with a 401/403
    before the hook payload was ever examined.
    """
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"{resource_id}/v1",
    )
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.consume_upload_token = AsyncMock(return_value=claims)
    upload_session_store_mock.try_lock_filename = AsyncMock(return_value=True)
    upload_session_store_mock.register_upload = AsyncMock()
    upload_session_store_mock.release_filename_lock = AsyncMock()

    registry_service_mock = MagicMock(spec=RegistryService)
    # pre-create reads resource.version to build the <resource_id>/<version> path.
    registry_service_mock.get_resource_and_assert_ownership.return_value.version = "v1"

    client = _build_client(
        upload_session_store=upload_session_store_mock,
        registry_service=registry_service_mock,
    )

    response = client.post(
        "/api/internal/tusd/hooks",
        json=_pre_create_body(resource_id=resource_id),
        # Explicitly no Authorization header — this is the contract under test.
    )

    assert response.status_code == 200
    body = response.json()
    # Successful pre-create returns a ChangeFileInfo block, not a RejectUpload.
    assert "RejectUpload" not in body or body["RejectUpload"] is False
    assert body["ChangeFileInfo"]["Storage"]["Path"] == (f"{resource_id}/v1/model.bin")
    # Authorization travelled through the upload-token path, not the auth chain.
    upload_session_store_mock.consume_upload_token.assert_awaited_once_with("token-1")
    registry_service_mock.get_resource_and_assert_ownership.assert_called_once()


def test_tusd_hooks_endpoint_dispatches_unknown_event_without_bearer_token() -> None:
    """An unknown event type must still produce a 200 (tusd-friendly no-op) when
    posted without a Bearer token. This catches regressions where the endpoint
    might gain a global auth dependency that rejects unauthenticated requests
    before per-event dispatch happens.
    """
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    registry_service_mock = MagicMock(spec=RegistryService)

    client = _build_client(
        upload_session_store=upload_session_store_mock,
        registry_service=registry_service_mock,
    )

    response = client.post(
        "/api/internal/tusd/hooks",
        json={
            "Type": "post-create",  # not in our handled set; should be a no-op
            "Event": {"Upload": {"ID": "abc", "Size": 0, "MetaData": {}}},
        },
    )

    assert response.status_code == 200
    # No per-event handler should have been invoked for an unknown event.
    upload_session_store_mock.consume_upload_token.assert_not_called()
    upload_session_store_mock.get_upload_session.assert_not_called()
