from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mism_env: str = Field(default="local", alias="MISM_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost/mism",
        alias="DATABASE_URL",
    )

    # All API + docs are mounted under this prefix so the UI can sit at "/".
    # Must start with "/" and not end with "/". Example: "/api".
    api_prefix: str = Field(default="/api", alias="API_PATH_PREFIX")

    upload_service_url: str = Field(default="http://localhost:8200", alias="UPLOAD_SERVICE_URL")
    upload_timeout_seconds: float = Field(default=60.0, alias="UPLOAD_TIMEOUT_SECONDS")

    execution_api_url: str = Field(
        default="http://localhost:8300",
        alias="EXECUTION_API_URL",
    )
    execution_timeout_seconds: float = Field(default=120.0, alias="EXECUTION_TIMEOUT_SECONDS")

    upload_chunk_size_bytes: int = Field(default=5 * 1024 * 1024, alias="UPLOAD_CHUNK_SIZE_BYTES")
    upload_retry_max_attempts: int = Field(default=3, alias="UPLOAD_RETRY_MAX_ATTEMPTS")
    upload_retry_backoff_seconds: float = Field(default=1.0, alias="UPLOAD_RETRY_BACKOFF_SECONDS")
    upload_retry_trailing_buffer_bytes: int = Field(
        default=15 * 1024 * 1024,
        alias="UPLOAD_RETRY_TRAILING_BUFFER_BYTES",
    )

    auth_mode: Literal["jwt", "oidc"] = Field(default="jwt", alias="AUTH_MODE")
    disable_auth: bool = Field(default=False, alias="DISABLE_AUTH")
    stub_upstream_services: bool = Field(default=False, alias="STUB_UPSTREAM_SERVICES")

    jwt_issuer: str = Field(default="", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="", alias="JWT_AUDIENCE")
    jwt_algorithms: str = Field(default="RS256", alias="JWT_ALGORITHMS")
    jwt_jwks_url: str = Field(default="", alias="JWT_JWKS_URL")
    jwt_public_key: str = Field(default="", alias="JWT_PUBLIC_KEY")

    oidc_issuer_url: str = Field(default="", alias="OIDC_ISSUER_URL")
    oidc_discovery_url: str = Field(default="", alias="OIDC_DISCOVERY_URL")
    oidc_audience: str = Field(default="", alias="OIDC_AUDIENCE")
    oidc_required_scopes: str = Field(default="", alias="OIDC_REQUIRED_SCOPES")
    oidc_jwks_ttl_seconds: int = Field(default=300, alias="OIDC_JWKS_TTL_SECONDS")

    @property
    def jwt_algorithm_list(self) -> list[str]:
        return [alg.strip() for alg in self.jwt_algorithms.split(",") if alg.strip()]

    @property
    def oidc_required_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.oidc_required_scopes.split(",") if scope.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
