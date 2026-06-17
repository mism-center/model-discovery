from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import ANY, AsyncMock, create_autospec

import pytest

from mismapi.api.internal import (
    _check_allowed_path,
    _handle_post_finish,
    _handle_pre_create,
    _handle_pre_terminate,
)
from mismapi.core.errors import APIError
from mismapi.schemas.auth import TusUploadRecord, UploadTokenClaims
from mismapi.schemas.tus import TusHookRequest
from mismapi.services.registry_service import RegistryService
from mismapi.services.upload_session_store_service import UploadSessionStoreService


def _make_upload_session_store_mock(
    *,
    claims: UploadTokenClaims | None = None,
    lock_acquired: bool = True,
    upload_record: TusUploadRecord | None = None,
) -> Any:
    """Build a fully-specced UploadSessionStoreService mock with sensible defaults.

    Every async method that the hook handlers touch is pre-wired with an
    AsyncMock so individual tests only have to override what they care about.
    """
    mock: Any = create_autospec(UploadSessionStoreService, instance=True, spec_set=True)
    mock.consume_upload_token = AsyncMock(return_value=claims)
    mock.try_lock_filename = AsyncMock(return_value=lock_acquired)
    mock.release_filename_lock = AsyncMock()
    mock.register_tus_upload = AsyncMock()
    mock.get_tus_upload = AsyncMock(return_value=upload_record)
    mock.delete_tus_upload = AsyncMock()
    mock.revoke_upload_token = AsyncMock()
    return mock


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


def _pre_terminate_payload(*, upload_id: str | None) -> TusHookRequest:
    return TusHookRequest.model_validate(
        {
            "Type": "pre-terminate",
            "Event": {
                "Upload": {
                    "ID": upload_id,
                    "Size": 1024,
                    "MetaData": {},
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
    upload_session_store_mock = _make_upload_session_store_mock(claims=claims)

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
    upload_session_store_mock.try_lock_filename.assert_awaited_once_with(
        resource_id=resource_id,
        filename="model.bin",
        owner=response.change_file_info.id,
    )
    upload_session_store_mock.register_tus_upload.assert_awaited_once_with(
        response.change_file_info.id,
        user_id="user-1",
        resource_id=resource_id,
        filename="model.bin",
    )
    upload_session_store_mock.release_filename_lock.assert_not_called()


async def test_handle_pre_create_returns_tus_rejection_for_missing_token(tmp_path: Path) -> None:
    payload = _pre_create_payload(resource_id="model-123", upload_token="")
    payload.event.upload.metadata.pop("upload_token")
    upload_session_store_mock = _make_upload_session_store_mock()
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
    upload_session_store_mock.try_lock_filename.assert_not_called()
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
    upload_session_store_mock = _make_upload_session_store_mock(claims=claims)
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
    # Lock was acquired before the existence check; it must be released so a
    # later upload of the same filename (after the user resolves the collision)
    # isn't blocked until TTL.
    upload_session_store_mock.release_filename_lock.assert_awaited_once()
    release_kwargs = upload_session_store_mock.release_filename_lock.call_args.kwargs
    assert release_kwargs["resource_id"] == resource_id
    assert release_kwargs["filename"] == "model.bin"
    # CAS owner must match what try_lock_filename was called with.
    lock_kwargs = upload_session_store_mock.try_lock_filename.call_args.kwargs
    assert release_kwargs["owner"] == lock_kwargs["owner"]


async def test_handle_pre_create_rejects_when_filename_lock_is_held(tmp_path: Path) -> None:
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    upload_session_store_mock = _make_upload_session_store_mock(
        claims=claims,
        lock_acquired=False,
    )
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, filename="model.bin"),
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is True
    assert response.http_response.status_code == 409
    assert "upload_in_progress" in response.http_response.body
    upload_session_store_mock.try_lock_filename.assert_awaited_once_with(
        resource_id=resource_id,
        filename="model.bin",
        owner=ANY,
    )
    # Did not acquire the lock, so we must not release it (would CAS-no-op but
    # is still wrong to call).
    upload_session_store_mock.release_filename_lock.assert_not_called()
    upload_session_store_mock.register_tus_upload.assert_not_called()


async def test_handle_pre_create_allows_concurrent_uploads_of_different_filenames(
    tmp_path: Path,
) -> None:
    """The lock is per `(resource_id, filename)`, not per resource — so the UI
    can upload multiple distinct files to the same model concurrently. We
    verify that by acquiring the lock for one filename and then attempting
    pre-create for a different filename on the same resource."""
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    upload_session_store_mock = _make_upload_session_store_mock(claims=claims)
    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, filename="weights.bin"),
        cast(UploadSessionStoreService, upload_session_store_mock),
        cast(RegistryService, service_mock),
        str(tmp_path),
    )

    assert response.reject_upload is False
    upload_session_store_mock.try_lock_filename.assert_awaited_once_with(
        resource_id=resource_id,
        filename="weights.bin",
        owner=ANY,
    )
    upload_session_store_mock.register_tus_upload.assert_awaited_once()


async def test_handle_pre_create_returns_tus_rejection_for_invalid_token(tmp_path: Path) -> None:
    resource_id = "model-123"
    upload_session_store_mock = _make_upload_session_store_mock()
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
    upload_session_store_mock.try_lock_filename.assert_not_called()
    upload_session_store_mock.register_tus_upload.assert_not_called()


async def test_handle_pre_create_sanitizes_filename(tmp_path: Path) -> None:
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"models/{resource_id}/files",
    )
    upload_session_store_mock = _make_upload_session_store_mock(claims=claims)
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
    upload_session_store_mock = _make_upload_session_store_mock(
        upload_record=TusUploadRecord(
            user_id="user-1", resource_id=resource_id, filename="model.bin"
        ),
    )
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
    upload_session_store_mock.release_filename_lock.assert_awaited_once_with(
        resource_id=resource_id,
        filename="model.bin",
        owner=upload_id,
    )
    upload_session_store_mock.revoke_upload_token.assert_awaited_once_with("token-1")


async def test_handle_post_finish_rejects_unknown_upload_id() -> None:
    resource_id = "model-123"
    upload_id = f"models/{resource_id}/files/.uploads/missing"
    upload_session_store_mock = _make_upload_session_store_mock(upload_record=None)
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
    upload_session_store_mock = _make_upload_session_store_mock(
        upload_record=TusUploadRecord(
            user_id="user-1", resource_id="model-123", filename="model.bin"
        ),
    )
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
    upload_session_store_mock = _make_upload_session_store_mock()
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


async def test_handle_pre_terminate_releases_lock_and_deletes_upload_record() -> None:
    resource_id = "model-123"
    upload_id = f"models/{resource_id}/files/.uploads/upload-1"
    upload_session_store_mock = _make_upload_session_store_mock(
        upload_record=TusUploadRecord(
            user_id="user-1", resource_id=resource_id, filename="model.bin"
        ),
    )

    response = await _handle_pre_terminate(
        _pre_terminate_payload(upload_id=upload_id),
        cast(UploadSessionStoreService, upload_session_store_mock),
    )

    assert response.reject_termination is False
    upload_session_store_mock.get_tus_upload.assert_awaited_once_with(upload_id)
    upload_session_store_mock.release_filename_lock.assert_awaited_once_with(
        resource_id=resource_id,
        filename="model.bin",
        owner=upload_id,
    )
    upload_session_store_mock.delete_tus_upload.assert_awaited_once_with(upload_id)


async def test_handle_pre_terminate_no_ops_when_upload_record_is_missing() -> None:
    upload_id = "models/model-123/files/.uploads/never-registered"
    upload_session_store_mock = _make_upload_session_store_mock(upload_record=None)

    response = await _handle_pre_terminate(
        _pre_terminate_payload(upload_id=upload_id),
        cast(UploadSessionStoreService, upload_session_store_mock),
    )

    # Don't block termination just because we have no record — tusd should
    # still clean up the bytes if the client asked it to.
    assert response.reject_termination is False
    upload_session_store_mock.release_filename_lock.assert_not_called()
    upload_session_store_mock.delete_tus_upload.assert_not_called()


async def test_handle_pre_terminate_no_ops_when_upload_id_is_missing() -> None:
    upload_session_store_mock = _make_upload_session_store_mock()

    response = await _handle_pre_terminate(
        _pre_terminate_payload(upload_id=None),
        cast(UploadSessionStoreService, upload_session_store_mock),
    )

    assert response.reject_termination is False
    upload_session_store_mock.get_tus_upload.assert_not_called()
    upload_session_store_mock.release_filename_lock.assert_not_called()
    upload_session_store_mock.delete_tus_upload.assert_not_called()
