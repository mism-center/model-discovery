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


class AuthCapabilities(BaseModel):
    """The calling principal's platform-wide OpenFGA role grants (MISM-291).

    Returned by ``GET /api/auth/capabilities`` so the UI can gate
    buttons/pages up front instead of guessing from ``/auth/me`` or
    403-probing individual endpoints. Kept separate from ``CurrentUser``
    (identity) since computing this requires OpenFGA round-trips that most
    ``/auth/me`` callers don't need, and it gives the UI a single place to
    refetch permissions after an admin grants/revokes a role mid-session.
    """

    uploader: bool
    upload_reviewer: bool
    image_checker: bool
    executor: bool


class LogoutResponse(BaseModel):
    """Result of ``POST /api/auth/logout``.

    ``end_session_url`` is the IdP's RP-initiated-logout URL when the
    configured OIDC provider exposes one. The UI is expected to navigate
    top-level to this URL so the IdP can clear its own session; when ``None``
    the local session has already been cleared and no further action is
    required.
    """

    end_session_url: str | None = None


class UploadTokenClaims(BaseModel):
    user_id: str
    max_bytes: int
    allowed_path: str


class TusUploadRecord(BaseModel):
    """
    Authorization context captured when tusd accepts an upload.

    `filename` is captured so `post-finish` / `pre-terminate` can release the
    `(resource_id, filename)` lock that `pre-create` acquired to serialize
    concurrent uploads targeting the same destination path.
    """

    user_id: str
    resource_id: str
    filename: str
