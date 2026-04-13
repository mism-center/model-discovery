import logging
import secrets

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from mismapi.auth.oidc import (
    OIDCDiscoveryLoader,
    build_authorize_url,
    exchange_code_for_tokens,
    generate_pkce_pair,
)
from mismapi.auth.session import SessionStore
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

PKCE_STATE_TTL_SECONDS = 300
LOGIN_PATH = "/api/auth/login"


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    session_store: SessionStore = request.app.state.session_store
    discovery_loader: OIDCDiscoveryLoader = request.app.state.oidc_discovery_loader

    discovery = await discovery_loader.load()
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()

    await session_store.set_ephemeral(
        key=state,
        value=code_verifier,
        ttl_seconds=PKCE_STATE_TTL_SECONDS,
    )

    authorize_url = build_authorize_url(
        discovery=discovery,
        settings=settings,
        state=state,
        code_challenge=code_challenge,
    )
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    if not code or not state:
        raise APIError(
            status_code=400,
            code="auth_callback_invalid",
            detail="Missing code or state parameter.",
        )

    settings: Settings = request.app.state.settings
    session_store: SessionStore = request.app.state.session_store
    discovery_loader: OIDCDiscoveryLoader = request.app.state.oidc_discovery_loader

    code_verifier = await session_store.get_ephemeral(key=state)
    if code_verifier is None:
        logger.warning("auth_state_invalid_or_expired state=%s", state)
        return RedirectResponse(url=LOGIN_PATH, status_code=302)

    discovery = await discovery_loader.load()
    token_response = await exchange_code_for_tokens(
        discovery=discovery,
        settings=settings,
        code=code,
        code_verifier=code_verifier,
    )

    from mismapi.auth.oidc_auth_validator import OIDCAuthValidator

    auth_validator: OIDCAuthValidator = request.app.state.auth_validator
    await auth_validator.verify_identity(token_response.id_token)

    session_id = await session_store.create(
        {
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
            "id_token": token_response.id_token,
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

    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        await session_store.delete(session_id)

    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response
