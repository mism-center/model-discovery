"""OIDC session-token refresh orchestration.

Owns the two responsibilities that previously lived as free functions in
:mod:`mismapi.auth.base`:

* ``refresh`` — unconditionally refresh the IdP tokens for an existing session
  record and persist the merged result.
* ``maybe_proactively_refresh`` — refresh only if the stored access token is
  within the configured skew window of expiry; otherwise return the session
  record untouched.

Collaborators are injected at construction (``settings``, ``session_store``,
``oidc_service``) so handlers can swap the refresher via
``dependency_overrides`` without monkey-patching module globals.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from mismapi.auth.oidc_service import OIDCService
from mismapi.auth.session import SessionStore
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionRefresher:
    """Refreshes OIDC session tokens against a :class:`OIDCService`."""

    settings: Settings
    session_store: SessionStore
    oidc_service: OIDCService

    async def refresh(
        self,
        *,
        session_id: str,
        session_data: dict[str, str],
        refresh_token: str,
    ) -> dict[str, str]:
        token_response = await self.oidc_service.refresh(refresh_token=refresh_token)
        merged = {**session_data, "access_token": token_response.access_token}
        if token_response.refresh_token:
            merged["refresh_token"] = token_response.refresh_token
        if token_response.id_token:
            merged["id_token"] = token_response.id_token
        ttl_sec = (
            token_response.expires_in
            if token_response.expires_in > 0
            else self.settings.session_ttl_seconds
        )
        merged["expires_at"] = str(int(time.time()) + ttl_sec)
        await self.session_store.replace(session_id, merged)
        return merged

    async def maybe_proactively_refresh(
        self,
        *,
        session_id: str,
        session_data: dict[str, str],
    ) -> dict[str, str]:
        if self.settings.auth_mode != "oidc":
            return session_data
        refresh_token = session_data.get("refresh_token", "")
        if not refresh_token:
            return session_data
        expires_raw = session_data.get("expires_at", "")
        try:
            expires_at = int(str(expires_raw).strip())
        except ValueError:
            return session_data
        now = int(time.time())
        skew = max(0, self.settings.oidc_access_token_refresh_skew_seconds)
        if expires_at - now > skew:
            return session_data
        try:
            return await self.refresh(
                session_id=session_id,
                session_data=session_data,
                refresh_token=refresh_token,
            )
        except APIError:
            logger.warning("oidc_proactive_refresh_failed session_id_prefix=%s", session_id[:8])
            return session_data
