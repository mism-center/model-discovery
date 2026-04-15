import logging
import secrets
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from mismapi.auth.oidc import (
    OIDCDiscoveryLoader,
    exchange_code_for_tokens,
    generate_code_verifier,
)
from mismapi.auth.session import SessionStore
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

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
async def login(request: Request) -> RedirectResponse:
    session_store: SessionStore = request.app.state.session_store
    discovery_loader: OIDCDiscoveryLoader = request.app.state.oidc_discovery_loader

    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()

    await session_store.set_ephemeral(
        key=state,
        value=code_verifier,
        ttl_seconds=PKCE_STATE_TTL_SECONDS,
    )

    authorize_url = await discovery_loader.create_authorization_url(
        state=state,
        code_verifier=code_verifier,
    )
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    settings: Settings = request.app.state.settings

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
        base = (settings.oidc_post_login_redirect_uri or "").strip() or LOGIN_PATH
        sep = "&" if "?" in base else "?"
        redirect_url = f"{base}{sep}{urlencode(params)}"
        return RedirectResponse(url=redirect_url, status_code=302)

    if not code or not state:
        raise APIError(
            status_code=400,
            code="auth_callback_invalid",
            detail="Missing code or state parameter.",
        )

    session_store: SessionStore = request.app.state.session_store
    discovery_loader: OIDCDiscoveryLoader = request.app.state.oidc_discovery_loader

    code_verifier = await session_store.get_ephemeral(key=state)
    if code_verifier is None:
        logger.warning(
            "auth_state_invalid_or_expired state=%s",
            _redact_oauth_state_for_log(state),
        )
        return RedirectResponse(url=LOGIN_PATH, status_code=302)

    discovery = await discovery_loader.load()
    token_response = await exchange_code_for_tokens(
        discovery=discovery,
        settings=settings,
        code=code,
        code_verifier=code_verifier,
        state=state,
    )

    from mismapi.auth.oidc_auth_validator import OIDCAuthValidator

    auth_validator: OIDCAuthValidator = request.app.state.auth_validator
    await auth_validator.verify_identity(token_response.id_token)

    ttl_sec = (
        token_response.expires_in if token_response.expires_in > 0 else settings.session_ttl_seconds
    )
    expires_at = str(int(time.time()) + ttl_sec)

    session_id = await session_store.create(
        {
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
            "id_token": token_response.id_token,
            "expires_at": expires_at,
        }
    )

    response = RedirectResponse(url=settings.oidc_post_login_redirect_uri, status_code=302)
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
async def logout(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    session_store: SessionStore = request.app.state.session_store
    discovery_loader: OIDCDiscoveryLoader = request.app.state.oidc_discovery_loader

    session_id = request.cookies.get(settings.session_cookie_name)
    id_token_hint = ""
    if session_id:
        session_data = await session_store.get(session_id)
        if session_data:
            id_token_hint = session_data.get("id_token") or session_data.get("access_token") or ""
        await session_store.delete(session_id)

    def _cleared_cookie_response(resp: Response) -> Response:
        resp.delete_cookie(
            key=settings.session_cookie_name,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return resp

    discovery = await discovery_loader.load()
    if discovery.end_session_endpoint and id_token_hint:
        logout_url = discovery.build_end_session_url(
            settings,
            id_token_hint=id_token_hint,
        )
        response = RedirectResponse(url=logout_url, status_code=302)
        return _cleared_cookie_response(response)

    response = JSONResponse(content={"status": "logged_out"})
    return _cleared_cookie_response(response)
