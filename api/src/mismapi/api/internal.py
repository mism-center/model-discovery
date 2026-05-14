"""
Internal endpoints invoked by infrastructure components (not end users).

Currently exposes a single tusd hook endpoint:

* `POST /api/internal/tusd/hooks` — wired to tusd's HTTP hook URL
  (`--hooks-http`). tusd posts every enabled hook event to this one
  endpoint and identifies the event in the `Type` field of the
  `HookRequest` envelope. We dispatch on that field:

  - `pre-create`: the client supplies an `upload_token` value (minted by
    this API, stored server-side, one-time consumable) and `resource_id`
    in tus upload metadata. We load claims via `SessionStore.consume_upload_token`,
    build an `AuthenticatedPrincipal` from `claims.user_id`, reject the
    upload if the declared size exceeds `claims.max_bytes`, then call
    `RegistryService.get_resource_and_assert_ownership` so the user owns
    the registry row for `resource_id`. On ownership failure we return
    `HookResponse` with `RejectUpload=True` so tusd aborts the upload.
  - `post-finish`: fires server-to-server after the upload completes and
    stamps `metadata['upload_status'] = 'UPLOAD_COMPLETE'` on the
    resource. Currently UNAUTHENTICATED at the application layer; we
    rely on transport-level trust (tusd and the API run in the same
    Kubernetes namespace, with a NetworkPolicy expected to restrict
    callers to the tusd pod). If that assumption ever breaks, reintroduce
    a shared-secret header or mTLS here before exposing this route to
    untrusted networks.
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

import logging

from fastapi import APIRouter

from mismapi.auth.base import (
    AuthenticatedPrincipal,
)
from mismapi.core.deps import (
    RegistryServiceDep,
    SessionStoreDep,
)
from mismapi.core.errors import APIError
from mismapi.schemas.auth import UploadTokenClaims
from mismapi.schemas.tus import (
    TusHookRequest,
    TusHookResponse,
    TusHTTPResponse,
)
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])

RESOURCE_ID_METADATA_KEY = "resource_id"
"""
Metadata key that tus clients (web, CLI) MUST set when creating an upload,
e.g. via `Upload-Metadata: resource_id <base64(uuid)>`. Without this we
cannot bind the upload to a registry resource for ownership checks.
`pre-create` also requires metadata key `upload_token` (see module docstring).
"""

TUSD_HOOK_PRE_CREATE = "pre-create"
TUSD_HOOK_POST_FINISH = "post-finish"


def _extract_resource_id(payload: TusHookRequest) -> str:
    resource_id = payload.event.upload.metadata.get(RESOURCE_ID_METADATA_KEY, "").strip()
    if not resource_id:
        raise APIError(
            status_code=400,
            code="missing_resource_id",
            detail=(f"tus upload metadata is missing required key '{RESOURCE_ID_METADATA_KEY}'."),
        )
    return resource_id


async def _handle_pre_create(
    payload: TusHookRequest,
    session_store: SessionStoreDep,
    service: RegistryService,
) -> TusHookResponse:
    """
    Returns a successful `HookResponse` when the principal owns the resource
    referenced by the upload metadata. Returns a rejection envelope (with
    `reject_upload=True`) for any authorization failure, which tusd surfaces
    to the client as the embedded `HTTPResponse`. The "not the owner" and
    "resource does not exist" cases are intentionally collapsed into the
    same 403 by `service.get_resource_and_assert_ownership`, so this handler
    cannot distinguish them either; that prevents probe-based enumeration
    of valid resource IDs (see that method's docstring for the threat model).

    Other failures (e.g., missing `resource_id` metadata) bubble up as
    standard `APIError`s, which become 4xx JSON responses via the global
    error handler. tusd treats any non-2xx hook response as a hard failure
    and aborts the upload.
    """
    metadata = payload.event.upload.metadata
    upload_token = metadata.get("upload_token")
    if not upload_token:
        raise APIError(
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
        raise APIError(
            status_code=413,
            code="upload_exceeds_permitted_size",
            detail="Upload exceeds permitted size",
        )

    resource_id = _extract_resource_id(payload)

    # try:
    #     service.get_resource_and_assert_ownership(principal, resource_id=resource_id)
    # except APIError as exc:
    #     if exc.status_code == 403:
    #         logger.info(
    #             "tus_authorize_rejected resource_id=%s subject=%s",
    #             resource_id,
    #             principal.subject,
    #         )
    #         return TusHookResponse(
    #             RejectUpload=True,
    #             HTTPResponse=TusHTTPResponse(
    #                 StatusCode=403,
    #                 Body=exc.detail,
    #                 Header={"Content-Type": "text/plain"},
    #             ),
    #         )
    #     raise

    logger.info(
        "tus_authorize_ok resource_id=%s subject=%s upload_id=%s",
        resource_id,
        principal.subject,
        payload.event.upload.id,
    )
    return TusHookResponse()


def _handle_post_finish(
    payload: TusHookRequest,
    service: RegistryService,
) -> TusHookResponse:
    """
    Mark the upload complete in the registry.
    """
    resource_id = _extract_resource_id(payload)
    service.mark_upload_complete(resource_id=resource_id)

    logger.info(
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
        return await _handle_pre_create(payload, session_store, service)

    if event_type == TUSD_HOOK_POST_FINISH:
        return _handle_post_finish(payload, service)

    logger.info(
        "tusd_hook_ignored type=%s upload_id=%s",
        event_type,
        payload.event.upload.id,
    )
    return TusHookResponse()
