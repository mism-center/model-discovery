"""
Internal endpoints invoked by infrastructure components (not end users).

Currently exposes a single tusd hook endpoint:

* `POST /api/internal/tusd/hooks` — wired to tusd's HTTP hook URL
  (`--hooks-http`). tusd posts every enabled hook event to this one
  endpoint and identifies the event in the `Type` field of the
  `HookRequest` envelope. We dispatch on that field:

  - `pre-create`: the client supplies an `upload_token` value (minted by
    this API, stored in Redis for `UPLOAD_TOKEN_TTL_SECONDS`), `resource_id`,
    and `filename` in tus upload metadata. We consume claims via
    `SessionStore.consume_upload_token` (atomically deleting the key so the
    token is single-use). We then build an `AuthenticatedPrincipal` from
    `claims.user_id`, reject the upload if the declared size exceeds
    `claims.max_bytes`, then call `RegistryService.get_resource_and_assert_ownership`
    so the user owns the model registry row for `resource_id`. On success,
    the file is stored flat at `models/{resource_id}/files/{filename}`. On
    ownership failure, invalid filename, or filename collision, we return
    `HookResponse` with `RejectUpload=True` so tusd aborts the upload.
  - `post-finish`: fires server-to-server after the upload completes and
    stamps `metadata['upload_status'] = 'UPLOAD_COMPLETE'` on the
    model resource. When `upload_token` is still present in upload metadata,
    the token key is removed from Redis (`revoke_upload_token`) as a harmless
    best-effort cleanup. Production deployments must keep this endpoint
    reachable only from tusd inside the cluster so public traffic cannot forge
    completion hooks.
  - any other event type: 200 no-op. tusd should only POST events that
    are listed in `--hooks-enabled-events`, but we tolerate unknown
    events to stay forward-compatible.

The endpoint accepts the full tusd `HookRequest` envelope as JSON and
returns the `HookResponse` shape (with `RejectUpload` and `HTTPResponse`)
tusd expects: see https://tus.github.io/tusd/advanced-topics/hooks/.

This endpoint is intentionally mounted under `/api/internal` (not
`/api/v1`) because the v1 router enforces a blanket `require_principal`
dependency: it does not fit `post-finish` (no user in the request) and it
does not fit `pre-create`, which authenticates via upload metadata and the
session store instead of `Authorization` / session cookies on the hook
request.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pathvalidate import sanitize_filename

from mismapi.auth.base import (
    AuthenticatedPrincipal,
)
from mismapi.core.deps import (
    RegistryServiceDep,
    SessionStoreDep,
    SettingsDep,
)
from mismapi.core.errors import APIError
from mismapi.schemas.auth import UploadTokenClaims
from mismapi.schemas.tus import (
    FileInfoChanges,
    Storage,
    TusHookRequest,
    TusHookResponse,
    TusHTTPResponse,
)
from mismapi.services.registry_service import RegistryService
from mismapi.utils import UPLOAD_ALLOWED_PATH_TEMPLATE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"], include_in_schema=False)

RESOURCE_ID_METADATA_KEY = "resource_id"
FILENAME_METADATA_KEY = "filename"
"""
Metadata keys that tus clients (web, CLI) MUST set when creating an upload.
Without `resource_id` we cannot bind the upload to a registry resource for
ownership checks. Without `filename` we cannot preserve the user's original
file basename in tusd storage. `pre-create` also requires metadata key
`upload_token` (see module docstring).
"""

TUSD_HOOK_PRE_CREATE = "pre-create"
TUSD_HOOK_POST_FINISH = "post-finish"


def _reject_upload(*, upload_id: str, status_code: int, code: str, detail: str) -> TusHookResponse:
    logger.info(
        "tus_authorize_rejected upload_id=%s status=%s code=%s detail=%s",
        upload_id,
        status_code,
        code,
        detail,
    )
    return TusHookResponse(
        RejectUpload=True,
        HTTPResponse=TusHTTPResponse(
            StatusCode=status_code,
            Body=json.dumps({"error": {"code": code, "detail": detail}}),
            Header={"Content-Type": "application/json"},
        ),
    )


def _upload_file_path(resource_id: str, filename: str) -> str:
    base_path = UPLOAD_ALLOWED_PATH_TEMPLATE.format(resource_id=resource_id)
    return f"{base_path}/{filename}"


def _extract_sanitized_filename(payload: TusHookRequest) -> str:
    raw_filename = payload.event.upload.metadata.get(FILENAME_METADATA_KEY, "").strip()
    if not raw_filename:
        raise APIError(
            status_code=400,
            code="missing_filename",
            detail="Upload filename is missing. Please choose a file and try again.",
        )

    filename = str(
        sanitize_filename(
            raw_filename,
            replacement_text="_",
            platform="universal",
            max_len=255,
            validate_after_sanitize=True,
        )
    ).strip()
    if not filename or filename in {".", ".."}:
        raise APIError(
            status_code=400,
            code="invalid_filename",
            detail="Upload filename is not valid. Please rename the file and try again.",
        )
    return filename


def _assert_upload_file_does_not_exist(storage_mount_path: str, upload_file_path: str) -> None:
    mount_root = Path(storage_mount_path).resolve()
    target_path = (mount_root / upload_file_path).resolve()
    if not target_path.is_relative_to(mount_root):
        raise APIError(
            status_code=400,
            code="upload_path_invalid",
            detail="Upload file path resolves outside the storage mount.",
        )

    if target_path.exists() or target_path.is_symlink():
        raise APIError(
            status_code=409,
            code="upload_file_exists",
            detail=(
                f"A file named '{target_path.name}' already exists for this model. "
                "Please choose a different filename or remove the existing file before uploading."
            ),
        )


def _extract_resource_id(payload: TusHookRequest) -> str:
    resource_id = payload.event.upload.metadata.get(RESOURCE_ID_METADATA_KEY, "").strip()
    if not resource_id:
        raise APIError(
            status_code=400,
            code="missing_resource_id",
            detail=(f"tus upload metadata is missing required key '{RESOURCE_ID_METADATA_KEY}'."),
        )
    return resource_id


def _check_allowed_path(claims: UploadTokenClaims, resource_id: str, upload_id: str) -> bool:
    allowed_path = claims.allowed_path
    expected_allowed_path = UPLOAD_ALLOWED_PATH_TEMPLATE.format(resource_id=resource_id)
    if allowed_path != expected_allowed_path:
        logger.debug(
            "tus_authorize_failed upload_id=%s resource_id=%s allowed_path=%s "
            + "expected_allowed_path=%s",
            upload_id,
            resource_id,
            allowed_path,
            expected_allowed_path,
        )
        return False
    return True


async def _handle_pre_create(
    payload: TusHookRequest,
    session_store: SessionStoreDep,
    service: RegistryService,
    storage_mount_path: str,
) -> TusHookResponse:
    """
    Return a successful `HookResponse` when the principal owns the model, the
    file is within the allowed number of bytes, the upload token is valid, and
    the file path is within the allowed file path from the upload token.

    Expected auth/validation failures are represented as tus-native
    `RejectUpload` responses. That keeps the hook HTTP status 2xx so tusd can
    return the intended client-facing status instead of treating the hook call
    itself as a failed internal dependency.
    """
    metadata = payload.event.upload.metadata
    upload_token = metadata.get("upload_token")
    upload_id = payload.event.upload.id or ""
    if not upload_token:
        return _reject_upload(
            upload_id=upload_id,
            status_code=400,
            code="missing_upload_token",
            detail="Upload token is missing.",
        )

    # Extract resource ID and filename from the payload
    try:
        resource_id = _extract_resource_id(payload)
        filename = _extract_sanitized_filename(payload)
    except APIError as exc:
        return _reject_upload(
            upload_id=upload_id,
            status_code=exc.status_code,
            code=exc.code,
            detail=exc.detail,
        )

    # Verify the upload token and extract claims
    try:
        claims: UploadTokenClaims = await session_store.consume_upload_token(upload_token)
    except APIError as exc:
        return _reject_upload(
            upload_id=upload_id,
            status_code=exc.status_code,
            code=exc.code,
            detail=exc.detail,
        )

    principal = AuthenticatedPrincipal(
        subject=claims.user_id,
        issuer="discovery-api",
        audience="discovery-api",
        scopes=set(),
    )

    # Verify the file size is within the allowed limit
    if payload.event.upload.size is None or (payload.event.upload.size > claims.max_bytes):
        return _reject_upload(
            upload_id=upload_id,
            status_code=413,
            code="upload_exceeds_permitted_size",
            detail="Upload exceeds permitted size",
        )

    # Verify the upload path is allowed (must be under the correct resource ID)
    if not _check_allowed_path(claims, resource_id, upload_id):
        return _reject_upload(
            upload_id=upload_id,
            status_code=403,
            code="upload_path_invalid",
            detail="Upload file does not have expected resource ID",
        )

    try:
        service.get_resource_and_assert_ownership(principal, resource_id=resource_id)
    except APIError as exc:
        return _reject_upload(
            upload_id=upload_id,
            status_code=exc.status_code,
            code=exc.code,
            detail=exc.detail,
        )

    upload_file_path = _upload_file_path(resource_id, filename)
    try:
        _assert_upload_file_does_not_exist(storage_mount_path, upload_file_path)
    except APIError as exc:
        return _reject_upload(
            upload_id=upload_id,
            status_code=exc.status_code,
            code=exc.code,
            detail=exc.detail,
        )

    logger.debug(
        "tus_authorize_ok resource_id=%s subject=%s upload_id=%s upload_path=%s",
        resource_id,
        principal.subject,
        upload_id,
        upload_file_path,
    )

    return TusHookResponse(
        ChangeFileInfo=FileInfoChanges(
            Storage=Storage(Path=upload_file_path),
        )
    )


async def _handle_post_finish(
    payload: TusHookRequest,
    service: RegistryService,
    session_store: SessionStoreDep,
) -> TusHookResponse:
    """
    Mark the upload complete in the registry and drop the upload token from
    Redis when tusd still forwards it in metadata (so the slot does not linger
    until TTL after a successful upload).
    """
    resource_id = _extract_resource_id(payload)
    service.mark_upload_complete(resource_id=resource_id)

    upload_token = payload.event.upload.metadata.get("upload_token")
    if upload_token:
        await session_store.revoke_upload_token(upload_token)

    logger.debug(
        "tus_complete_ok resource_id=%s upload_id=%s size=%s",
        resource_id,
        payload.event.upload.id,
        payload.event.upload.size,
    )
    return TusHookResponse()


@router.post(
    "/tusd/hooks",
    response_model=TusHookResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def tusd_hooks(
    payload: TusHookRequest,
    session_store: SessionStoreDep,
    service: RegistryServiceDep,
    settings: SettingsDep,
) -> TusHookResponse:
    """
    Unified tusd HTTP hook endpoint.

    tusd is configured with a single `--hooks-http` URL pointing here and
    dispatches every enabled event to it. The event name lives in the
    `Type` field of the envelope; per-event behavior is handled by the
    `_handle_*` helpers above.

    """
    event_type = payload.type

    if event_type == TUSD_HOOK_PRE_CREATE:
        return await _handle_pre_create(
            payload,
            session_store,
            service,
            settings.irods_mount_path,
        )

    if event_type == TUSD_HOOK_POST_FINISH:
        return await _handle_post_finish(payload, service, session_store)

    logger.info(
        "tusd_hook_ignored type=%s upload_id=%s",
        event_type,
        payload.event.upload.id,
    )
    return TusHookResponse()
