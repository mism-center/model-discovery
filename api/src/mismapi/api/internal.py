"""
Internal endpoints invoked by infrastructure components (not end users).

Currently exposes a single tusd hook endpoint:

* `POST /api/internal/tusd/hooks` — wired to tusd's HTTP hook URL
  (`--hooks-http`). tusd posts every enabled hook event to this one
  endpoint and identifies the event in the `Type` field of the
  `HookRequest` envelope. We dispatch on that field:

  - `pre-create`: tusd is configured to forward the original client
    `Authorization` header (via `--hooks-http-forward-headers Authorization`),
    so we authenticate with the same machinery used by `/api/v1/*` and
    verify the principal owns the resource named in
    `Event.Upload.MetaData.resource_id`. A failed authorization returns a
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
dependency that does not fit the post-finish auth model (no user request
context at hook time).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.security import HTTPAuthorizationCredentials

from mismapi.auth.base import (
    AuthenticatedPrincipal,
    bearer_dependency,
    require_principal,
)
from mismapi.core.deps import (
    AuthValidatorDep,
    RegistryServiceDep,
    SessionRefresherDep,
    SessionStoreDep,
    SettingsDep,
)
from mismapi.core.errors import APIError
from mismapi.schemas.tus import TusHookRequest, TusHookResponse, TusHTTPResponse
from mismapi.services.registry_service import RegistryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])

RESOURCE_ID_METADATA_KEY = "resource_id"
"""
Metadata key that tus clients (web, CLI) MUST set when creating an upload,
e.g. via `Upload-Metadata: resource_id <base64(uuid)>`. Without this we
cannot bind the upload to a registry resource for ownership checks.
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


def _handle_pre_create(
    payload: TusHookRequest,
    principal: AuthenticatedPrincipal,
    service: RegistryService,
) -> TusHookResponse:
    """
    Returns a successful `HookResponse` when the principal owns the resource
    referenced by the upload metadata. Returns a rejection envelope (with
    `reject_upload=True`) for any authorization failure, which tusd surfaces
    to the client as the embedded `HTTPResponse`. The "not the owner" and
    "resource does not exist" cases are intentionally collapsed into the
    same 403 by `service.assert_owner`, so this handler cannot distinguish
    them either; that prevents probe-based enumeration of valid resource
    IDs (see the docstring on `assert_owner` for the threat model).

    Other failures (e.g., missing `resource_id` metadata) bubble up as
    standard `APIError`s, which become 4xx JSON responses via the global
    error handler. tusd treats any non-2xx hook response as a hard failure
    and aborts the upload.
    """
    resource_id = _extract_resource_id(payload)

    try:
        service.get_resource_and_assert_ownership(principal, resource_id=resource_id)
    except APIError as exc:
        if exc.status_code == 403:
            logger.info(
                "tus_authorize_rejected resource_id=%s subject=%s",
                resource_id,
                principal.subject,
            )
            return TusHookResponse(
                RejectUpload=True,
                HTTPResponse=TusHTTPResponse(
                    StatusCode=403,
                    Body=exc.detail,
                    Header={"Content-Type": "text/plain"},
                ),
            )
        raise

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
    request: Request,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    validator: AuthValidatorDep,
    session_refresher: SessionRefresherDep,
    service: RegistryServiceDep,
    credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
) -> TusHookResponse:
    """
    Unified tusd HTTP hook endpoint.

    tusd is configured with a single `--hooks-http` URL pointing here and
    dispatches every enabled event to it. The event name lives in the
    `Type` field of the envelope; per-event behavior is handled by the
    `_handle_*` helpers above.

    Auth dependencies (`session_store`, `validator`, `session_refresher`,
    `credentials`) are declared at the route level rather than inside an
    `AuthenticatedPrincipalDep`-style dependency because only the
    `pre-create` branch needs a user principal. Doing so allows
    `post-finish` to pass through with no `Authorization` header.
    """
    event_type = payload.type

    if event_type == TUSD_HOOK_PRE_CREATE:
        principal = await require_principal(
            request=request,
            settings=settings,
            session_store=session_store,
            validator=validator,
            session_refresher=session_refresher,
            credentials=credentials,
        )
        return _handle_pre_create(payload, principal, service)

    if event_type == TUSD_HOOK_POST_FINISH:
        return _handle_post_finish(payload, service)

    logger.info(
        "tusd_hook_ignored type=%s upload_id=%s",
        event_type,
        payload.event.upload.id,
    )
    return TusHookResponse()
