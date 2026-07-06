import logging
import time

import jwt
from authlib.integrations.base_client.errors import MismatchingStateError
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from mismapi.auth.base import AuthenticatedPrincipalDep
from mismapi.auth.return_to import DEFAULT_LANDING_PATH, resolve_return_to
from mismapi.core.deps import (
    OIDCServiceDep,
    SessionStoreDep,
    SettingsDep,
)
from mismapi.core.errors import APIError
from mismapi.schemas.auth import CurrentUser, LogoutResponse, OidcSessionRecord
from mismapi.utils import merge_query_params

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

LOGIN_PATH = "/api/auth/login"
AUTH_ERROR_DESCRIPTION_MAX_LEN = 120
RETURN_TO_SESSION_KEY = "return_to"


@router.get("/login")
async def login(
    request: Request,
    oidc_service: OIDCServiceDep,
    return_to_key: str = "",
    return_to_query: str = "",
) -> RedirectResponse:
    # Carry return_to through the IdP round-trip in the SessionMiddleware
    # cookie (already required by Authlib). Read again in /callback.
    if return_to_key:
        request.session[RETURN_TO_SESSION_KEY] = {
            "key": return_to_key,
            "query": return_to_query,
        }
    else:
        request.session.pop(RETURN_TO_SESSION_KEY, None)
    return await oidc_service.authorize_redirect(request)


@router.get("/callback")
async def callback(
    request: Request,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    oidc_service: OIDCServiceDep,
    code: str = "",
    state: str = "",
) -> RedirectResponse:
    # Pop early: also clears the entry on the idp_error / mismatched-state paths
    # so a stale return_to can't leak into a subsequent, unrelated login attempt.
    return_to = request.session.pop(RETURN_TO_SESSION_KEY, None)

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
        base = settings.oidc_post_login_redirect_uri or DEFAULT_LANDING_PATH
        return RedirectResponse(url=merge_query_params(base, params), status_code=302)

    if not code or not state:
        raise APIError(
            status_code=400,
            code="auth_callback_invalid",
            detail="Missing code or state parameter.",
        )

    try:
        token_response = await oidc_service.authorize_access_token(request)
    except MismatchingStateError as exc:
        logger.warning("auth_state_invalid_or_expired error=%s", exc)
        return RedirectResponse(url=LOGIN_PATH, status_code=302)

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

    if return_to and return_to.get("key"):
        landing = resolve_return_to(return_to.get("key"), return_to.get("query"))
    else:
        landing = settings.oidc_post_login_redirect_uri or DEFAULT_LANDING_PATH
    response = RedirectResponse(url=landing, status_code=302)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.production_mode,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.get("/me")
async def me(
    request: Request,
    principal: AuthenticatedPrincipalDep,
    settings: SettingsDep,
    session_store: SessionStoreDep,
) -> CurrentUser:
    """Return the current authenticated user."""
    claims: dict[str, object] = {}
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        session_data = await session_store.get(session_id)
        if session_data and session_data.id_token:
            try:
                claims = jwt.decode(
                    session_data.id_token,
                    options={"verify_signature": False},
                )
            except jwt.InvalidTokenError:
                claims = {}

    def _str_or_none(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    return CurrentUser(
        sub=principal.subject,
        iss=principal.issuer,
        scopes=sorted(principal.scopes),
        email=_str_or_none(claims.get("email")),
        name=_str_or_none(claims.get("name")),
        preferred_username=_str_or_none(claims.get("preferred_username")),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    settings: SettingsDep,
    session_store: SessionStoreDep,
    oidc_service: OIDCServiceDep,
) -> LogoutResponse:
    """Clear the local session and surface the IdP end-session URL if any.

    Always returns JSON so the UI can decide whether to navigate top-level
    to the IdP. Avoids cross-origin redirect responses that `fetch` can't
    read.
    """
    session_id = request.cookies.get(settings.session_cookie_name)
    id_token_hint = ""
    if session_id:
        session_data = await session_store.get(session_id)
        if session_data:
            id_token_hint = session_data.id_token or session_data.access_token or ""
        await session_store.delete(session_id)

    end_session_url: str | None = None
    if id_token_hint:
        end_session_url = await oidc_service.build_end_session_url(id_token_hint=id_token_hint)

    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.production_mode,
        samesite="lax",
    )
    return LogoutResponse(end_session_url=end_session_url)
