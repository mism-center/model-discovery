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

    mism_env: str = Field(default="local", alias="MISM_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost/mism",
        alias="DATABASE_URL",
    )

    upload_service_url: BaseUrl = Field(default="http://localhost:8200", alias="UPLOAD_SERVICE_URL")
    upload_timeout_seconds: float = Field(default=60.0, alias="UPLOAD_TIMEOUT_SECONDS")

    upload_chunk_size_bytes: int = Field(default=5 * 1024 * 1024, alias="UPLOAD_CHUNK_SIZE_BYTES")
    upload_retry_max_attempts: int = Field(default=3, alias="UPLOAD_RETRY_MAX_ATTEMPTS")
    upload_retry_backoff_seconds: float = Field(default=1.0, alias="UPLOAD_RETRY_BACKOFF_SECONDS")
    upload_retry_trailing_buffer_bytes: int = Field(
        default=15 * 1024 * 1024,
        alias="UPLOAD_RETRY_TRAILING_BUFFER_BYTES",
    )

    auth_mode: Literal["oidc"] = Field(default="oidc", alias="AUTH_MODE")
    disable_auth: bool = Field(default=False, alias="DISABLE_AUTH")
    stub_upstream_services: bool = Field(default=False, alias="STUB_UPSTREAM_SERVICES")

    oidc_issuer_url: str = Field(default="", alias="OIDC_ISSUER_URL")
    oidc_discovery_url: str = Field(default="", alias="OIDC_DISCOVERY_URL")
    oidc_audience: str = Field(default="", alias="OIDC_AUDIENCE")
    oidc_required_scopes: str = Field(default="", alias="OIDC_REQUIRED_SCOPES")
    oidc_jwks_ttl_seconds: int = Field(default=300, alias="OIDC_JWKS_TTL_SECONDS")
    oidc_client_id: str = Field(default="", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(default="", alias="OIDC_REDIRECT_URI")
    oidc_post_login_redirect_uri: str = Field(default="", alias="OIDC_POST_LOGIN_REDIRECT_URI")
    oidc_post_logout_redirect_uri: str = Field(default="", alias="OIDC_POST_LOGOUT_REDIRECT_URI")
    oidc_jwt_leeway_seconds: int = Field(default=30, alias="OIDC_JWT_LEEWAY_SECONDS")

    production_mode: bool = Field(default=False, alias="PRODUCTION_MODE")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    session_ttl_seconds: int = Field(default=3600, alias="SESSION_TTL_SECONDS")
    session_cookie_name: str = Field(default="mism_session", alias="SESSION_COOKIE_NAME")

    @property
    def oidc_required_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.oidc_required_scopes.split(",") if scope.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
