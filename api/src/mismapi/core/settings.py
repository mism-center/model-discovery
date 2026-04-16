from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mism_env: str = Field(default="local", alias="MISM_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    search_service_url: str = Field(default="http://localhost:8100", alias="SEARCH_SERVICE_URL")
    upload_service_url: str = Field(default="http://localhost:8200", alias="UPLOAD_SERVICE_URL")
    search_timeout_seconds: float = Field(default=10.0, alias="SEARCH_TIMEOUT_SECONDS")
    upload_timeout_seconds: float = Field(default=60.0, alias="UPLOAD_TIMEOUT_SECONDS")

    upload_chunk_size_bytes: int = Field(default=5 * 1024 * 1024, alias="UPLOAD_CHUNK_SIZE_BYTES")
    upload_retry_max_attempts: int = Field(default=3, alias="UPLOAD_RETRY_MAX_ATTEMPTS")
    upload_retry_backoff_seconds: float = Field(default=1.0, alias="UPLOAD_RETRY_BACKOFF_SECONDS")
    upload_retry_trailing_buffer_bytes: int = Field(
        default=15 * 1024 * 1024,
        alias="UPLOAD_RETRY_TRAILING_BUFFER_BYTES",
    )

    auth_mode: Literal["jwt", "oidc"] = Field(default="oidc", alias="AUTH_MODE")
    stub_upstream_services: bool = Field(default=False, alias="STUB_UPSTREAM_SERVICES")

    jwt_issuer: str = Field(default="", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="", alias="JWT_AUDIENCE")
    jwt_algorithms: str = Field(default="RS256", alias="JWT_ALGORITHMS")
    jwt_jwks_url: str = Field(default="", alias="JWT_JWKS_URL")
    jwt_public_key: str = Field(default="", alias="JWT_PUBLIC_KEY")
    jwt_leeway_seconds: int = Field(default=0, alias="JWT_LEEWAY_SECONDS")

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
    oidc_token_exchange_audience: str = Field(
        default="helx-exec-platform",
        alias="OIDC_TOKEN_EXCHANGE_AUDIENCE",
        description=(
            "Target audience for token exchange at the IdP (Keycloak: often the HeLx Execution "
            "Platform resource server client id or configured audience). Requires client policies "
            "that allow this gateway client (OIDC_CLIENT_ID) to exchange a user access token into "
            "that audience."
        ),
    )
    oidc_token_exchange_scopes: str = Field(
        default="",
        alias="OIDC_TOKEN_EXCHANGE_SCOPES",
        description="Optional space-delimited scopes to request on the exchanged access token.",
    )
    oidc_access_token_refresh_skew_seconds: int = Field(
        default=120,
        alias="OIDC_ACCESS_TOKEN_REFRESH_SKEW_SECONDS",
        description=(
            "When calling upstream token exchange, refresh the user session access token if it "
            "expires within this many seconds."
        ),
    )
    helx_exec_platform_base_url: str = Field(
        default="",
        alias="HELX_EXEC_PLATFORM_BASE_URL",
        description="Base URL of the HeLx Execution Platform (server-to-server calls).",
    )
    helx_exec_platform_jwt_audience: str = Field(
        default="",
        alias="HELX_EXEC_PLATFORM_JWT_AUDIENCE",
        description=(
            "Expected JWT aud claim on the exchanged token before calling the HeLx Execution "
            "Platform. If empty, OIDC_TOKEN_EXCHANGE_AUDIENCE is used."
        ),
    )
    helx_exec_platform_timeout_seconds: float = Field(
        default=60.0,
        alias="HELX_EXEC_PLATFORM_TIMEOUT_SECONDS",
    )

    production_mode: bool = Field(default=False, alias="PRODUCTION_MODE")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    session_ttl_seconds: int = Field(default=3600, alias="SESSION_TTL_SECONDS")
    session_cookie_name: str = Field(default="mism_session", alias="SESSION_COOKIE_NAME")

    @property
    def jwt_algorithm_list(self) -> list[str]:
        return [alg.strip() for alg in self.jwt_algorithms.split(",") if alg.strip()]

    @property
    def oidc_required_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.oidc_required_scopes.split(",") if scope.strip()]

    @property
    def oidc_token_exchange_scopes_parts(self) -> list[str]:
        return [part for part in self.oidc_token_exchange_scopes.split() if part]

    @property
    def helx_exec_platform_jwt_audience_effective(self) -> str:
        if self.helx_exec_platform_jwt_audience.strip():
            return self.helx_exec_platform_jwt_audience.strip()
        return self.oidc_token_exchange_audience.strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
