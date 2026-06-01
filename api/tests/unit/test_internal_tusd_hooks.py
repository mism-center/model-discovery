from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, create_autospec

from mismapi.api.internal import _check_allowed_path, _handle_pre_create
from mismapi.auth.session import SessionStore
from mismapi.core.errors import APIError
from mismapi.schemas.auth import UploadTokenClaims
from mismapi.schemas.tus import TusHookRequest
from mismapi.services.registry_service import RegistryService


def _pre_create_payload(
    *,
    resource_id: str,
    upload_token: str = "token-1",
    filename: str = "model.bin",
    upload_id: str | None = "",
) -> TusHookRequest:
    return TusHookRequest.model_validate(
        {
            "Type": "pre-create",
            "Event": {
                "Upload": {
                    "ID": upload_id,
                    "Size": 1024,
                    "MetaData": {
                        "resource_id": resource_id,
                        "upload_token": upload_token,
                        "filename": filename,
                    },
                }
            },
        }
    )


def test_check_allowed_path_accepts_exact_resource_path() -> None:
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=1024,
        allowed_path="models/model-123/files",
    )

    assert _check_allowed_path(claims, resource_id="model-123", upload_id="upload-1")


def test_check_allowed_path_rejects_non_matching_path() -> None:
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=1024,
        allowed_path="models/model-abc/files",
    )

    assert not _check_allowed_path(claims, resource_id="model-123", upload_id="upload-1")


async def test_handle_pre_create_sets_flat_storage_path_from_filename(tmp_path: Path) -> None:
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    session_store_mock: Any = create_autospec(SessionStore, instance=True, spec_set=True)
    session_store_mock.consume_upload_token = AsyncMock(return_value=claims)

    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, upload_token="token-1"),
        cast(SessionStore, session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    session_store_mock.consume_upload_token.assert_awaited_once_with("token-1")
    service_mock.get_resource_and_assert_ownership.assert_called_once()

    principal = service_mock.get_resource_and_assert_ownership.call_args.args[0]
    assert principal.subject == "user-1"
    assert (
        service_mock.get_resource_and_assert_ownership.call_args.kwargs["resource_id"]
        == resource_id
    )

    assert response.change_file_info is not None
    assert response.change_file_info.id is None
    assert response.change_file_info.storage is not None
    assert response.change_file_info.storage.path == f"models/{resource_id}/files/model.bin"


async def test_handle_pre_create_returns_tus_rejection_for_missing_token(tmp_path: Path) -> None:
    payload = _pre_create_payload(resource_id="model-123", upload_token="")
    payload.event.upload.metadata.pop("upload_token")
    session_store_mock: Any = create_autospec(SessionStore, instance=True, spec_set=True)
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        payload,
        cast(SessionStore, session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 400
    assert "missing_upload_token" in response.http_response.body
    session_store_mock.consume_upload_token.assert_not_called()


async def test_handle_pre_create_rejects_existing_filename(tmp_path: Path) -> None:
    resource_id = "model-123"
    existing_file = tmp_path / "models" / resource_id / "files" / "model.bin"
    existing_file.parent.mkdir(parents=True)
    existing_file.write_bytes(b"already here")

    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    session_store_mock: Any = create_autospec(SessionStore, instance=True, spec_set=True)
    session_store_mock.consume_upload_token = AsyncMock(return_value=claims)
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, filename="model.bin"),
        cast(SessionStore, session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 409
    assert "already exists for this model" in response.http_response.body


async def test_handle_pre_create_returns_tus_rejection_for_invalid_token(tmp_path: Path) -> None:
    resource_id = "model-123"
    session_store_mock: Any = create_autospec(SessionStore, instance=True, spec_set=True)
    session_store_mock.consume_upload_token = AsyncMock(
        side_effect=APIError(
            status_code=401,
            code="auth_upload_token_invalid",
            detail="Upload token is invalid or has expired",
        )
    )
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id),
        cast(SessionStore, session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 401
    assert "auth_upload_token_invalid" in response.http_response.body
    service_mock.get_resource_and_assert_ownership.assert_not_called()


async def test_handle_pre_create_sanitizes_filename(tmp_path: Path) -> None:
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    session_store_mock: Any = create_autospec(SessionStore, instance=True, spec_set=True)
    session_store_mock.consume_upload_token = AsyncMock(return_value=claims)
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, filename="nested/model.bin"),
        cast(SessionStore, session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.change_file_info is not None
    assert response.change_file_info.storage is not None
    assert response.change_file_info.storage.path == f"models/{resource_id}/files/nested_model.bin"
