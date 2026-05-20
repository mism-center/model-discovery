from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AfterValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_trailing_slash(value: str) -> str:
    return value.rstrip("/")


"""
URL used as a prefix for path joining (trailing slash stripped).

Whitespace is stripped globally via Pydantic's `str_strip_whitespace`.
"""
BaseUrl = Annotated[str, AfterValidator(_strip_trailing_slash)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    deploy_type: Literal["cloud", "local"] = Field(default="cloud", alias="DEPLOY_TYPE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost/mism",
        alias="DATABASE_URL",
    )

    tusd_base_url: BaseUrl = Field(default="http://localhost:8080", alias="TUSD_BASE_URL")

    auth_mode: Literal["oidc"] = Field(default="oidc", alias="AUTH_MODE")
    disable_auth: bool = Field(default=False, alias="DISABLE_AUTH")
    stub_upstream_services: bool = Field(default=False, alias="STUB_UPSTREAM_SERVICES")

    oidc_issuer_url: BaseUrl = Field(default="", alias="OIDC_ISSUER_URL")
    oidc_discovery_url: BaseUrl = Field(default="", alias="OIDC_DISCOVERY_URL")
    oidc_audience: str = Field(default="", alias="OIDC_AUDIENCE")
    oidc_required_scopes: str = Field(default="", alias="OIDC_REQUIRED_SCOPES")
    oidc_jwks_ttl_seconds: int = Field(default=300, alias="OIDC_JWKS_TTL_SECONDS")
    oidc_client_id: str = Field(default="", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(default="", alias="OIDC_REDIRECT_URI")
    oidc_post_login_redirect_uri: str = Field(default="", alias="OIDC_POST_LOGIN_REDIRECT_URI")
    oidc_post_logout_redirect_uri: str = Field(default="", alias="OIDC_POST_LOGOUT_REDIRECT_URI")
    oidc_jwt_leeway_seconds: int = Field(default=30, alias="OIDC_JWT_LEEWAY_SECONDS")
    oidc_cookie_signing_secret: str = Field(default="", alias="OIDC_COOKIE_SIGNING_SECRET")

    # Master switch for production-only behaviors. Set True only in production.
    # Currently controls:
    #   - `Secure` attribute on every cookie we emit (OAuth-state cookie via
    #     `SessionMiddleware` in `main.py`, Redis session cookie set in the
    #     `/api/auth/callback` handler, logout deletion cookie in
    #     `/api/auth/logout`). Browsers refuse to send `Secure` cookies over
    #     HTTP except for literal `localhost`, so leaving this False locally
    #     is required for non-localhost dev hosts (/etc/hosts aliases,
    #     127.0.0.1 in some browsers, Safari) to avoid a
    #     `MismatchingStateError` on the OAuth callback.
    #   - Uvicorn access-log redaction (`core/uvicorn_access_log.py`). When
    #     True, the `RedactedAccessFormatter` replaces every query-param
    #     *value* with `<redacted>` while keeping keys intact, so secrets or
    #     PII passed via query strings (`?token=...`, `?email=...`) do not
    #     leak into stdout/aggregator pipelines. Keys remain visible to
    #     preserve operability.
    # When adding a new behavior gated by this flag, append it to the list above.
    production_mode: bool = Field(default=False, alias="PRODUCTION_MODE")

    redis_url: BaseUrl = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    session_ttl_seconds: int = Field(default=3600, alias="SESSION_TTL_SECONDS")
    upload_token_ttl_seconds: int = Field(default=900, alias="UPLOAD_TOKEN_TTL_SECONDS")
    session_cookie_name: str = Field(default="mism_session", alias="SESSION_COOKIE_NAME")

    # Short-lived cookie that holds the Authlib-managed OAuth state / PKCE / nonce
    # blob during the `/api/auth/login` -> `/api/auth/callback` handshake. Must
    # NOT equal `session_cookie_name`; collision causes `SessionMiddleware` to
    # overwrite or delete the Redis session ID cookie set by the callback,
    # producing a 401 on every subsequent authenticated request.
    oauth_state_cookie_name: str = Field(
        default="mism_oauth_state", alias="OAUTH_STATE_COOKIE_NAME"
    )
    oauth_state_cookie_max_age_seconds: int = Field(
        default=600, alias="OAUTH_STATE_COOKIE_MAX_AGE_SECONDS"
    )

    @property
    def oidc_required_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.oidc_required_scopes.split(",") if scope.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
