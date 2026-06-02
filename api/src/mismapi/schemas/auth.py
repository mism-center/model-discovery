from pydantic import BaseModel, ConfigDict


class OidcSessionRecord(BaseModel):
    """OIDC tokens and metadata stored for a browser session in `SessionStore`."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str = ""
    id_token: str = ""
    expires_at: str = ""


class CurrentUser(BaseModel):
    """Authenticated user view returned by ``GET /api/auth/me``."""

    sub: str
    iss: str
    scopes: list[str]
    email: str | None = None
    name: str | None = None
    preferred_username: str | None = None


class LogoutResponse(BaseModel):
    """Result of ``POST /api/auth/logout``.

    ``end_session_url`` is the IdP's RP-initiated-logout URL when the
    configured OIDC provider exposes one. The UI is expected to navigate
    top-level to this URL so the IdP can clear its own session; when ``None``
    the local session has already been cleared and no further action is
    required.
    """

    end_session_url: str | None = None
