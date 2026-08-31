from functools import lru_cache
from typing import Annotated, Any, Literal

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

    def __init__(self, **data: Any) -> None:
        """
        Build settings from explicit kwargs plus configured env sources.

        `BaseSettings` allows required fields to be omitted from the constructor
        when they are supplied by environment variables or `.env`, but some
        static analyzers model it like a normal Pydantic model constructor. This
        explicit signature matches the runtime behavior without weakening the
        field definitions themselves.
        """
        super().__init__(**data)

    # Main
    deploy_type: Literal["cloud", "local"] = Field(default="cloud", alias="DEPLOY_TYPE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(alias="DATABASE_URL")
    stub_upstream_services: bool = Field(default=False, alias="STUB_UPSTREAM_SERVICES")
    # All API + docs are mounted under this prefix so the UI can sit at "/".
    # Use "" to mount at root; otherwise prefer a leading slash without a trailing slash.
    api_prefix: str = Field(default="/api", alias="API_PATH_PREFIX")

    # tusd
    tusd_base_url: BaseUrl = Field(alias="TUSD_BASE_URL")
    upload_max_bytes: int = Field(default=1024 * 1024 * 500, alias="UPLOAD_MAX_BYTES", gt=0)

    # iRODS
    # On-pod path where the iRODS PVC is mounted (see chart values.yaml ->
    # irods.pvc.mountPath). Resource location_uris of the form
    # "irods:///<rel>" or "/irods/<rel>" resolve to "{irods_mount_path}/<rel>".
    irods_mount_path: str = Field(default="/irods", alias="IRODS_MOUNT_PATH")

    # The annotation job pod and this API pod mount the same iRODS PVC from
    # different pods; there's a brief window after the job is reported
    # "succeeded" where the written metadata-package files aren't yet visible
    # through this pod's mount. Bounded retry absorbs that propagation lag
    # before surfacing a 404 — see RegistryService._metadata_package_dir.
    metadata_package_retry_max_attempts: int = Field(
        default=4, alias="METADATA_PACKAGE_RETRY_MAX_ATTEMPTS"
    )
    metadata_package_retry_backoff_seconds: float = Field(
        default=2.0, alias="METADATA_PACKAGE_RETRY_BACKOFF_SECONDS"
    )

    # Upload service
    upload_service_url: BaseUrl = Field(default="http://localhost:8200", alias="UPLOAD_SERVICE_URL")
    upload_timeout_seconds: float = Field(default=60.0, alias="UPLOAD_TIMEOUT_SECONDS")
    # "local" → write straight to the iRODS PVC (LocalFileUploadClient).
    # "http"  → forward to a real upload service (UploadServiceClient).
    upload_backend: Literal["local", "http"] = Field(default="local", alias="UPLOAD_BACKEND")
    upload_chunk_size_bytes: int = Field(default=5 * 1024 * 1024, alias="UPLOAD_CHUNK_SIZE_BYTES")
    upload_retry_max_attempts: int = Field(default=3, alias="UPLOAD_RETRY_MAX_ATTEMPTS")
    upload_retry_backoff_seconds: float = Field(default=1.0, alias="UPLOAD_RETRY_BACKOFF_SECONDS")
    upload_retry_trailing_buffer_bytes: int = Field(
        default=15 * 1024 * 1024,
        alias="UPLOAD_RETRY_TRAILING_BUFFER_BYTES",
    )

    # Execution service
    execution_api_url: str = Field(
        default="http://localhost:8300",
        alias="EXECUTION_API_URL",
    )
    execution_timeout_seconds: float = Field(default=120.0, alias="EXECUTION_TIMEOUT_SECONDS")

    # Annotation job defaults — used to build the execution payload for batch runs.
    annotation_job_image: str = Field(
        default="helxplatform/bio-pi-agent-runner:latest",
        alias="ANNOTATION_JOB_IMAGE",
    )
    annotation_job_cpus: str = Field(default="1", alias="ANNOTATION_JOB_CPUS")
    annotation_job_memory: str = Field(default="4Gi", alias="ANNOTATION_JOB_MEMORY")
    annotation_job_prompt: str = Field(default="", alias="ANNOTATION_JOB_PROMPT")

    annotation_openai_base_url: str = Field(default="", alias="ANNOTATION_OPENAI_BASE_URL")
    annotation_model: str = Field(default="gpt-5.6-luna", alias="ANNOTATION_MODEL")

    # CAIRNS service integration
    # Empty disables the integration, endpoints return 503 when disabled.
    cairns_api_url: BaseUrl = Field(default="", alias="CAIRNS_API_URL")
    # CAIRNS runs retrieval plus an LLM synthesis step per request; observed
    # latencies are tens of seconds, so this ceiling is far above the HTTP norm.
    cairns_timeout_seconds: float = Field(default=180.0, alias="CAIRNS_TIMEOUT_SECONDS", gt=0)

    # Authentication
    auth_mode: Literal["oidc"] = Field(default="oidc", alias="AUTH_MODE")
    disable_auth: bool = Field(default=False, alias="DISABLE_AUTH")
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

    # OIDC
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

    # Redis
    redis_url: BaseUrl = Field(alias="REDIS_URL")
    session_ttl_seconds: int = Field(default=3600, alias="SESSION_TTL_SECONDS")
    upload_token_ttl_seconds: int = Field(default=900, alias="UPLOAD_TOKEN_TTL_SECONDS")
    tus_upload_ttl_seconds: int = Field(default=3600, alias="TUS_UPLOAD_TTL_SECONDS")
    session_cookie_name: str = Field(default="mism_session", alias="SESSION_COOKIE_NAME")

    # Production mode
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

    @property
    def oidc_required_scope_list(self) -> list[str]:
        return [scope.strip() for scope in self.oidc_required_scopes.split(",") if scope.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
