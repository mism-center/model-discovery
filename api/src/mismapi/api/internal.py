"""
Internal endpoints invoked by infrastructure components (not end users).

Currently exposes a single tusd hook endpoint:

* `POST /api/internal/tusd/hooks` — wired to tusd's HTTP hook URL
  (`--hooks-http`). tusd posts every enabled hook event to this one
  endpoint and identifies the event in the `Type` field of the
  `HookRequest` envelope. We dispatch on that field:

  - `pre-create`: the client supplies an `upload_token` value (minted by
    this API, stored in Redis for `UPLOAD_TOKEN_TTL_SECONDS`) and `resource_id`
    in tus upload metadata. We consume claims via `SessionStore.consume_upload_token`
    (atomically deleting the key so the token is single-use). We then build an
    `AuthenticatedPrincipal` from `claims.user_id`, reject the
    upload if the declared size exceeds `claims.max_bytes`, then call
    `RegistryService.get_resource_and_assert_ownership` so the user owns
    the model registry row for `resource_id`. On ownership failure we return
    `HookResponse` with `RejectUpload=True` so tusd aborts the upload.
  - `post-finish`: fires server-to-server after the upload completes and
    stamps `metadata['upload_status'] = 'UPLOAD_COMPLETE'` on the
    model resource. When `upload_token` is still present in upload metadata,
    the token key is removed from Redis (`revoke_upload_token`) as a harmless
    best-effort cleanup. The endpoint verifies `X-MISM-TUSD-HOOK-SECRET` when
    `TUSD_HOOK_SECRET` is configured; production startup requires that secret
    so public ingress traffic cannot forge completion hooks.
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

import hmac
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Header

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
"""
Metadata key that tus clients (web, CLI) MUST set when creating an upload,
e.g. via `Upload-Metadata: resource_id <base64(uuid)>`. Without this we
cannot bind the upload to a registry resource for ownership checks.
`pre-create` also requires metadata key `upload_token` (see module docstring).
"""

TUSD_HOOK_PRE_CREATE = "pre-create"
TUSD_HOOK_POST_FINISH = "post-finish"
TUSD_HOOK_SECRET_HEADER = "X-MISM-TUSD-HOOK-SECRET"


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


def _verify_tusd_hook_secret(settings_secret: str, provided_secret: str | None) -> None:
    if not settings_secret:
        raise APIError(
            status_code=500,
            code="internal_error",
            detail="tusd hook secret is not configured.",
        )
    if provided_secret is None or not hmac.compare_digest(settings_secret, provided_secret):
        raise APIError(
            status_code=401,
            code="tusd_hook_unauthorized",
            detail="Missing or invalid tusd hook secret.",
        )


def _upload_file_path(resource_id: str, upload_id: str) -> str:
    base_path = UPLOAD_ALLOWED_PATH_TEMPLATE.format(resource_id=resource_id)
    safe_upload_id = upload_id.strip()
    if not safe_upload_id or "/" in safe_upload_id or safe_upload_id in {".", ".."}:
        raise APIError(
            status_code=400,
            code="invalid_upload_id",
            detail="tusd upload ID is missing or invalid.",
        )
    return f"{base_path}/{safe_upload_id}"


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
) -> TusHookResponse:
    """
    Return a successful `HookResponse` when the principal owns the model.

    Expected auth/validation failures are represented as tus-native
    `RejectUpload` responses. That keeps the hook HTTP status 2xx so tusd can
    return the intended client-facing status instead of treating the hook call
    itself as a failed internal dependency.
    """
    metadata = payload.event.upload.metadata
    upload_token = metadata.get("upload_token")
    upload_id = payload.event.upload.id
    if not upload_token:
        return _reject_upload(
            upload_id=upload_id,
            status_code=400,
            code="missing_upload_token",
            detail="Upload token is missing.",
        )
    claims: UploadTokenClaims = await session_store.consume_upload_token(upload_token)
    principal = AuthenticatedPrincipal(
        subject=claims.user_id,
        issuer="discovery-api",
        audience="discovery-api",
        scopes=set(),
    )
    if payload.event.upload.size is None or (payload.event.upload.size > claims.max_bytes):
        return _reject_upload(
            upload_id=upload_id,
            status_code=413,
            code="upload_exceeds_permitted_size",
            detail="Upload exceeds permitted size",
        )

    resource_id = _extract_resource_id(payload)

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

    logger.debug(
        "tus_authorize_ok resource_id=%s subject=%s upload_id=%s",
        resource_id,
        principal.subject,
        payload.event.upload.id,
    )

    try:
        file_base_path = UPLOAD_ALLOWED_PATH_TEMPLATE.format(resource_id=resource_id)
    except APIError as e:
        return _reject_upload(
            upload_id=upload_id,
            status_code=e.status_code,
            code=e.code,
            detail=e.detail,
        )
    return TusHookResponse(
        ChangeFileInfo=FileInfoChanges(
            ID=file_base_path,
            Storage=Storage(Path=_upload_file_path(resource_id, upload_id)),
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
)
async def tusd_hooks(
    payload: TusHookRequest,
    session_store: SessionStoreDep,
    service: RegistryServiceDep,
    settings: SettingsDep,
    tusd_hook_secret: Annotated[str | None, Header(alias=TUSD_HOOK_SECRET_HEADER)] = None,
) -> TusHookResponse:
    """
    Unified tusd HTTP hook endpoint.

    tusd is configured with a single `--hooks-http` URL pointing here and
    dispatches every enabled event to it. The event name lives in the
    `Type` field of the envelope; per-event behavior is handled by the
    `_handle_*` helpers above.

    """
    _verify_tusd_hook_secret(settings.tusd_hook_secret, tusd_hook_secret)

    event_type = payload.type

    if event_type == TUSD_HOOK_PRE_CREATE:
        return await _handle_pre_create(payload, session_store, service)

    if event_type == TUSD_HOOK_POST_FINISH:
        return await _handle_post_finish(payload, service, session_store)

    logger.info(
        "tusd_hook_ignored type=%s upload_id=%s",
        event_type,
        payload.event.upload.id,
    )
    return TusHookResponse()
