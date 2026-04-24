import logging
import secrets
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from mismapi.auth.oidc_types import generate_code_verifier
from mismapi.core.deps import (
    OIDCServiceDep,
    OIDCValidatorDep,
    SessionStoreDep,
    SettingsDep,
)
from mismapi.core.errors import APIError
from mismapi.schemas.auth import OidcSessionRecord
from mismapi.utils import merge_query_params

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

PKCE_STATE_TTL_SECONDS = 300
LOGIN_PATH = "/api/auth/login"
AUTH_ERROR_DESCRIPTION_MAX_LEN = 120


def _redact_oauth_state_for_log(state: str) -> str:
    if len(state) <= 8:
        return "…"
    return f"{state[:8]}…"


@router.get("/login")
async def login(
    session_store: SessionStoreDep,
    oidc_service: OIDCServiceDep,
) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()

    await session_store.set_ephemeral(
        key=state,
        value=code_verifier,
        ttl_seconds=PKCE_STATE_TTL_SECONDS,
    )

    authorize_url = await oidc_service.build_authorization_url(
        state=state,
        code_verifier=code_verifier,
    )
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/callback")
async def callback(
    request: Request,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    oidc_service: OIDCServiceDep,
    auth_validator: OIDCValidatorDep,
    code: str = "",
    state: str = "",
) -> RedirectResponse:
    idp_error = request.query_params.get("error")
    if idp_error:
        raw_desc = request.query_params.get("error_description") or ""
        desc_trunc = raw_desc[:AUTH_ERROR_DESCRIPTION_MAX_LEN]
        logger.warning(
            "auth_idp_error error=%s error_description=%s",
            idp_error,
            desc_trunc,
        )
        params: dict[str, str] = {"auth_error": idp_error}
        if desc_trunc:
            params["auth_error_description"] = desc_trunc
        base = settings.oidc_post_login_redirect_uri or LOGIN_PATH
        return RedirectResponse(url=merge_query_params(base, params), status_code=302)

    if not code or not state:
        raise APIError(
            status_code=400,
            code="auth_callback_invalid",
            detail="Missing code or state parameter.",
        )

    code_verifier = await session_store.get_ephemeral(key=state)
    if code_verifier is None:
        logger.warning(
            "auth_state_invalid_or_expired state=%s",
            _redact_oauth_state_for_log(state),
        )
        return RedirectResponse(url=LOGIN_PATH, status_code=302)

    token_response = await oidc_service.exchange_code(
        code=code,
        code_verifier=code_verifier,
        state=state,
    )

    await auth_validator.verify_identity(token_response.id_token)

    ttl_sec = (
        token_response.expires_in if token_response.expires_in > 0 else settings.session_ttl_seconds
    )
    expires_at = str(int(time.time()) + ttl_sec)

    session_id = await session_store.create(
        OidcSessionRecord(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            id_token=token_response.id_token,
            expires_at=expires_at,
        )
    )

    response = RedirectResponse(
        url=settings.oidc_post_login_redirect_uri or LOGIN_PATH,
        status_code=302,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    oidc_service: OIDCServiceDep,
) -> Response:
    session_id = request.cookies.get(settings.session_cookie_name)
    id_token_hint = ""
    if session_id:
        session_data = await session_store.get(session_id)
        if session_data:
            id_token_hint = session_data.id_token or session_data.access_token or ""
        await session_store.delete(session_id)

    def _cleared_cookie_response(resp: Response) -> Response:
        resp.delete_cookie(
            key=settings.session_cookie_name,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return resp

    if id_token_hint:
        logout_url = await oidc_service.build_end_session_url(id_token_hint=id_token_hint)
        if logout_url is not None:
            return _cleared_cookie_response(RedirectResponse(url=logout_url, status_code=302))

    return _cleared_cookie_response(JSONResponse(content={"status": "logged_out"}))
