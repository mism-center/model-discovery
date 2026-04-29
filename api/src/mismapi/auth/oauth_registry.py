"""
Authlib OAuth registry.

Owns the single Authlib `OAuth` instance and the registered OIDC client used
for every browser-side OAuth flow. The client wraps Authlib's `StarletteOAuth2App`.

Discovery + JWKS caching for *outbound* flows is handled internally by Authlib
via `server_metadata_url`. Inbound bearer-token validation continues to use
`mismapi.auth.jwks_cache.JWKSCache`, sourcing its `jwks_uri` through the same
registered client to avoid a second discovery cache.
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from mismapi.core.settings import Settings

OIDC_CLIENT_NAME = "oidc"


def build_oauth_registry(settings: Settings) -> OAuth:
    """Construct an `OAuth` registry with the project's OIDC client registered."""
    oauth = OAuth()
    oauth.register(
        name=OIDC_CLIENT_NAME,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        server_metadata_url=_resolve_server_metadata_url(settings),
        client_kwargs={
            "scope": "openid",
            "code_challenge_method": "S256",
        },
    )
    return oauth


def get_oidc_client(oauth: OAuth) -> StarletteOAuth2App:
    """Return the registered OIDC client, narrowing the dynamic type."""
    client = oauth.create_client(OIDC_CLIENT_NAME)
    if client is None:
        raise RuntimeError(f"OAuth client {OIDC_CLIENT_NAME!r} is not registered.")
    if not isinstance(client, StarletteOAuth2App):
        raise RuntimeError(
            f"OAuth client {OIDC_CLIENT_NAME!r} is not a StarletteOAuth2App "
            f"(got {type(client).__name__})."
        )
    return client


def _resolve_server_metadata_url(settings: Settings) -> str:
    """
    Pick the discovery URL Authlib will load on first use.

    Explicit `OIDC_DISCOVERY_URL` wins; otherwise derive it from the issuer.
    """
    if settings.oidc_discovery_url:
        return settings.oidc_discovery_url
    issuer = settings.oidc_issuer_url.rstrip("/")
    return f"{issuer}/.well-known/openid-configuration"
