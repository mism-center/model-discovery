from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, create_autospec

from mismapi.api.internal import _check_allowed_path, _handle_pre_create
from mismapi.auth.session import SessionStore
from mismapi.schemas.auth import UploadTokenClaims
from mismapi.schemas.tus import TusHookRequest
from mismapi.services.registry_service import RegistryService


def _pre_create_payload(*, resource_id: str, upload_token: str = "token-1") -> TusHookRequest:
    return TusHookRequest.model_validate(
        {
            "Type": "pre-create",
            "Event": {
                "Upload": {
                    "ID": "upload-1",
                    "Size": 1024,
                    "MetaData": {
                        "resource_id": resource_id,
                        "upload_token": upload_token,
                    },
                }
            },
        }
    )


def test_check_allowed_path_accepts_exact_resource_path() -> None:
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=1024,
        allowed_path="/models/model-123/files",
    )

    assert _check_allowed_path(claims, resource_id="model-123", upload_id="upload-1")


def test_check_allowed_path_rejects_non_matching_path() -> None:
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=1024,
        allowed_path="/models/model-abc/files",
    )

    assert not _check_allowed_path(claims, resource_id="model-123", upload_id="upload-1")


async def test_handle_pre_create_sets_change_file_info_paths() -> None:
    resource_id = "model-123"
    claims = UploadTokenClaims(
        user_id="user-1",
        max_bytes=10_000,
        allowed_path=f"/models/{resource_id}/files",
    )
    session_store_mock: Any = create_autospec(SessionStore, instance=True, spec_set=True)
    session_store_mock.validate_upload_token = AsyncMock(return_value=claims)

    service_mock: Any = create_autospec(RegistryService, instance=True, spec_set=True)

    response = await _handle_pre_create(
        _pre_create_payload(resource_id=resource_id, upload_token="token-1"),
        cast(SessionStore, session_store_mock),
        cast(RegistryService, service_mock),
    )

    session_store_mock.validate_upload_token.assert_awaited_once_with("token-1")
    service_mock.get_resource_and_assert_ownership.assert_called_once()

    principal = service_mock.get_resource_and_assert_ownership.call_args.args[0]
    assert principal.subject == "user-1"
    assert (
        service_mock.get_resource_and_assert_ownership.call_args.kwargs["resource_id"]
        == resource_id
    )

    assert response.change_file_info is not None
    assert response.change_file_info.id == f"models/{resource_id}/files"
    assert response.change_file_info.storage is not None
    assert response.change_file_info.storage.path == f"/models/{resource_id}/files/{resource_id}"
