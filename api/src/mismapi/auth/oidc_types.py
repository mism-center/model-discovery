"""
OIDC value types and flow-level constants.

All OIDC flow logic (authorization URL, code-for-token exchange, refresh,
end-session) lives in `mismapi.auth.oidc_service`. Discovery-document
caching lives in `mismapi.auth.oidc_discovery`. This module is deliberately
kept to pure data classes and small pure helpers so that it can be imported
from anywhere without dragging in `authlib` or `httpx` client machinery.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

TOKEN_ERROR_BODY_MAX_LEN = 256


@dataclass(frozen=True, slots=True)
class OIDCDiscoveryDocument:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str


@dataclass(frozen=True, slots=True)
class TokenResponse:
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


def generate_code_verifier() -> str:
    """PKCE `code_verifier` (high-entropy secret)."""
    return secrets.token_urlsafe(96)
