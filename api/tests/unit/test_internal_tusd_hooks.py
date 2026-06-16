from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, create_autospec

import pytest

from mismapi.api.internal import _check_allowed_path, _handle_post_finish, _handle_pre_create
from mismapi.core.errors import APIError
from mismapi.schemas.auth import TusUploadRecord, UploadTokenClaims
from mismapi.schemas.tus import TusHookRequest
from mismapi.services.registry_service import RegistryService
from mismapi.services.upload_session_store_service import UploadSessionStoreService


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


def _post_finish_payload(
    *,
    resource_id: str,
    upload_id: str | None = "models/model-123/files/.uploads/upload-1",
    upload_token: str = "token-1",
) -> TusHookRequest:
    return TusHookRequest.model_validate(
        {
            "Type": "post-finish",
            "Event": {
                "Upload": {
                    "ID": upload_id,
                    "Size": 1024,
                    "MetaData": {
                        "resource_id": resource_id,
                        "upload_token": upload_token,
                        "filename": "model.bin",
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
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.consume_upload_token = AsyncMock(return_value=claims)

    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, upload_token="token-1"),
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    upload_session_store_mock.consume_upload_token.assert_awaited_once_with("token-1")
    service_mock.get_resource_and_assert_ownership.assert_called_once()

    principal = service_mock.get_resource_and_assert_ownership.call_args.args[0]
    assert principal.subject == "user-1"
    assert (
        service_mock.get_resource_and_assert_ownership.call_args.kwargs["resource_id"]
        == resource_id
    )

    assert response.change_file_info is not None
    assert response.change_file_info.id is not None
    assert response.change_file_info.id.startswith(f"models/{resource_id}/files/.uploads/")
    assert response.change_file_info.storage is not None
    assert response.change_file_info.storage.path == f"models/{resource_id}/files/model.bin"
    upload_session_store_mock.register_tus_upload.assert_awaited_once_with(
        response.change_file_info.id,
        user_id="user-1",
        resource_id=resource_id,
    )


async def test_handle_pre_create_returns_tus_rejection_for_missing_token(tmp_path: Path) -> None:
    payload = _pre_create_payload(resource_id="model-123", upload_token="")
    payload.event.upload.metadata.pop("upload_token")
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        payload,
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 400
    assert "missing_upload_token" in response.http_response.body
    upload_session_store_mock.consume_upload_token.assert_not_called()
    upload_session_store_mock.register_tus_upload.assert_not_called()


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
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.consume_upload_token = AsyncMock(return_value=claims)
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, filename="model.bin"),
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 409
    assert "already exists for this model" in response.http_response.body
    upload_session_store_mock.register_tus_upload.assert_not_called()


async def test_handle_pre_create_returns_tus_rejection_for_invalid_token(tmp_path: Path) -> None:
    resource_id = "model-123"
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.consume_upload_token = AsyncMock(
        side_effect=APIError(
            status_code=401,
            code="auth_upload_token_invalid",
            detail="Upload token is invalid or has expired",
        )
    )
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id),
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 401
    assert "auth_upload_token_invalid" in response.http_response.body
    service_mock.get_resource_and_assert_ownership.assert_not_called()
    upload_session_store_mock.register_tus_upload.assert_not_called()


async def test_handle_pre_create_sanitizes_filename(tmp_path: Path) -> None:
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.consume_upload_token = AsyncMock(return_value=claims)
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, filename="nested/model.bin"),
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.change_file_info is not None
    assert response.change_file_info.id is not None
    assert response.change_file_info.id.startswith(f"models/{resource_id}/files/.uploads/")
    assert response.change_file_info.storage is not None
    assert response.change_file_info.storage.path == f"models/{resource_id}/files/nested_model.bin"


async def test_handle_post_finish_rechecks_stored_upload_owner_before_marking_complete() -> None:
    resource_id = "model-123"
    upload_id = f"models/{resource_id}/files/.uploads/upload-1"
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.get_tus_upload = AsyncMock(
        return_value=TusUploadRecord(user_id="user-1", resource_id=resource_id)
    )
    upload_session_store_mock.delete_tus_upload = AsyncMock()
    upload_session_store_mock.revoke_upload_token = AsyncMock()
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_post_finish(
        _post_finish_payload(resource_id=resource_id, upload_id=upload_id),
        cast(RegistryService, service_mock),
        cast(UploadSessionStoreService, upload_session_store_mock),
    )

    assert response.reject_upload is False
    upload_session_store_mock.get_tus_upload.assert_awaited_once_with(upload_id)
    service_mock.mark_upload_complete.assert_called_once()
    principal = service_mock.mark_upload_complete.call_args.args[0]
    assert principal.subject == "user-1"
    assert service_mock.mark_upload_complete.call_args.kwargs["resource_id"] == resource_id
    upload_session_store_mock.delete_tus_upload.assert_awaited_once_with(upload_id)
    upload_session_store_mock.revoke_upload_token.assert_awaited_once_with("token-1")


async def test_handle_post_finish_rejects_unknown_upload_id() -> None:
    resource_id = "model-123"
    upload_id = f"models/{resource_id}/files/.uploads/missing"
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.get_tus_upload = AsyncMock(return_value=None)
    upload_session_store_mock.delete_tus_upload = AsyncMock()
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    with pytest.raises(APIError) as exc_info:
        await _handle_post_finish(
            _post_finish_payload(resource_id=resource_id, upload_id=upload_id),
            cast(RegistryService, service_mock),
            cast(UploadSessionStoreService, upload_session_store_mock),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "not_authorized"
    service_mock.mark_upload_complete.assert_not_called()
    upload_session_store_mock.delete_tus_upload.assert_not_called()


async def test_handle_post_finish_rejects_resource_id_mismatch_for_upload_id() -> None:
    upload_id = "models/model-123/files/.uploads/upload-1"
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    upload_session_store_mock.get_tus_upload = AsyncMock(
        return_value=TusUploadRecord(user_id="user-1", resource_id="model-123")
    )
    upload_session_store_mock.delete_tus_upload = AsyncMock()
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    with pytest.raises(APIError) as exc_info:
        await _handle_post_finish(
            _post_finish_payload(resource_id="model-456", upload_id=upload_id),
            cast(RegistryService, service_mock),
            cast(UploadSessionStoreService, upload_session_store_mock),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "not_authorized"
    service_mock.mark_upload_complete.assert_not_called()
    upload_session_store_mock.delete_tus_upload.assert_not_called()


async def test_handle_post_finish_rejects_missing_upload_id() -> None:
    upload_session_store_mock: Any = create_autospec(
        UploadSessionStoreService, instance=True, spec_set=True
    )
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    with pytest.raises(APIError) as exc_info:
        await _handle_post_finish(
            _post_finish_payload(resource_id="model-123", upload_id=None),
            cast(RegistryService, service_mock),
            cast(UploadSessionStoreService, upload_session_store_mock),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "missing_upload_id"
    upload_session_store_mock.get_tus_upload.assert_not_called()
    service_mock.mark_upload_complete.assert_not_called()
