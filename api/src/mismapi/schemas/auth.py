from pydantic import BaseModel, ConfigDict


class OidcSessionRecord(BaseModel):
    """OIDC tokens and metadata stored for a browser session in `SessionStore`."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str = ""
    id_token: str = ""
    expires_at: str = ""
