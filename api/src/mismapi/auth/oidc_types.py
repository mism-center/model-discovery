"""
OIDC value types and flow-level constants.

OIDC discovery, JWKS handling, and the actual OAuth flow are owned by
Authlib via `mismapi.auth.oidc_service.OIDCService`. This module is
deliberately kept to pure value types so it can be imported anywhere
without dragging in `authlib` or `httpx`.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

TOKEN_ERROR_BODY_MAX_LEN = 256


class IdpServerMetadata(BaseModel):
    """Validated subset of an OIDC discovery document.

    Mirrors the OpenID Connect Discovery 1.0 spec plus the common
    OAuth 2.0 Authorization Server Metadata (RFC 8414) and RP-Initiated
    Logout extensions. Required fields are the ones our flows actually
    depend on (`issuer`, `authorization_endpoint`, `token_endpoint`,
    `jwks_uri`); empty strings are rejected via `min_length=1` because
    those flows would silently break on an empty value.

    Provider-specific extras (Microsoft Entra's `tenant_region_scope`,
    Keycloak's `frontchannel_logout_supported`, Authlib's `_loaded_at`
    sentinel, etc.) are accepted via `extra="allow"` so we never reject a
    well-formed payload that simply happens to include unfamiliar keys.
    """

    model_config = ConfigDict(extra="allow")

    issuer: str = Field(min_length=1)
    authorization_endpoint: str = Field(min_length=1)
    token_endpoint: str = Field(min_length=1)
    jwks_uri: str = Field(min_length=1)

    userinfo_endpoint: str | None = None
    end_session_endpoint: str | None = None
    revocation_endpoint: str | None = None
    introspection_endpoint: str | None = None

    response_types_supported: list[str] | None = None
    response_modes_supported: list[str] | None = None
    grant_types_supported: list[str] | None = None
    subject_types_supported: list[str] | None = None
    scopes_supported: list[str] | None = None
    claims_supported: list[str] | None = None
    id_token_signing_alg_values_supported: list[str] | None = None
    token_endpoint_auth_methods_supported: list[str] | None = None
    code_challenge_methods_supported: list[str] | None = None


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """Normalized result of a token exchange or refresh."""

    access_token: str
    refresh_token: str
    id_token: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class OIDCErrorCodes:
    """Flow-specific error codes for a single OIDC token endpoint operation."""

    http_status_failed: str
    unavailable: str
    invalid_response: str
    detail_failed: str
    detail_unavailable: str


CODE_EXCHANGE_ERRORS = OIDCErrorCodes(
    http_status_failed="auth_token_exchange_failed",
    unavailable="auth_token_exchange_unavailable",
    invalid_response="auth_token_exchange_invalid",
    detail_failed="OIDC token exchange failed.",
    detail_unavailable="OIDC token endpoint is unavailable.",
)

REFRESH_ERRORS = OIDCErrorCodes(
    http_status_failed="auth_token_refresh_failed",
    unavailable="auth_token_refresh_unavailable",
    invalid_response="auth_token_refresh_invalid",
    detail_failed="OIDC token refresh failed.",
    detail_unavailable="OIDC token endpoint is unavailable.",
)
