"""
OIDC session-token refresh orchestration.

Owns `refresh` — unconditionally refresh the IdP tokens for an existing session
record and persist the merged result — which previously lived as a free function
in `mismapi.auth.base`.

Collaborators are injected at construction (`settings`, `session_store`,
`oidc_service`) so handlers can swap the refresher via
`dependency_overrides` without monkey-patching module globals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from mismapi.auth.oidc_service import OIDCService
from mismapi.auth.session import SessionStore
from mismapi.core.settings import Settings
from mismapi.schemas.auth import OidcSessionRecord


@dataclass(slots=True)
class SessionRefresher:
    """Refreshes OIDC session tokens against a `OIDCService`."""

    settings: Settings
    session_store: SessionStore
    oidc_service: OIDCService

    async def refresh(
        self,
        *,
        session_id: str,
        session_data: OidcSessionRecord,
    ) -> OidcSessionRecord:
        token_response = await self.oidc_service.refresh(refresh_token=session_data.refresh_token)
        update: dict[str, str] = {
            "access_token": token_response.access_token,
            "expires_at": str(
                int(time.time())
                + (
                    token_response.expires_in
                    if token_response.expires_in > 0
                    else self.settings.session_ttl_seconds
                )
            ),
        }
        if token_response.refresh_token:
            update["refresh_token"] = token_response.refresh_token
        if token_response.id_token:
            update["id_token"] = token_response.id_token
        merged = session_data.model_copy(update=update)
        await self.session_store.replace(session_id, merged)
        return merged
