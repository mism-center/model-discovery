from pydantic import BaseModel, ConfigDict


class OidcSessionRecord(BaseModel):
    """OIDC tokens and metadata stored for a browser session in `SessionStore`."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str = ""
    id_token: str = ""
    expires_at: str = ""


class UploadTokenClaims(BaseModel):
    user_id: str
    max_bytes: int
    allowed_path: str


class TusUploadRecord(BaseModel):
    """Authorization context captured when tusd accepts an upload."""

    user_id: str
    resource_id: str
