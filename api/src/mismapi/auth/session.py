import logging
import secrets
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError
from redis.asyncio import Redis

from mismapi.schemas.auth import OidcSessionRecord

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    async def create(self, session_data: OidcSessionRecord) -> str: ...

    async def get(self, session_id: str) -> OidcSessionRecord | None: ...

    async def replace(self, session_id: str, session_data: OidcSessionRecord) -> None: ...

    async def delete(self, session_id: str) -> None: ...

    async def set_ephemeral(self, key: str, value: str, ttl_seconds: int) -> None: ...

    async def get_ephemeral(self, key: str) -> str | None: ...


SESSION_KEY_PREFIX = "session:"
OIDC_STATE_KEY_PREFIX = "oidc_state:"


@dataclass(slots=True)
class RedisSessionStore:
    redis: Redis
    session_ttl_seconds: int

    async def create(self, session_data: OidcSessionRecord) -> str:
        session_id = secrets.token_urlsafe(32)
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.redis.set(key, session_data.model_dump_json(), ex=self.session_ttl_seconds)
        return session_id

    async def get(self, session_id: str) -> OidcSessionRecord | None:
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        raw = await self.redis.get(key)
        if raw is None:
            return None
        try:
            return OidcSessionRecord.model_validate_json(raw)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                "session_store_invalid_payload session_id_prefix=%s error=%s",
                session_id[:8],
                exc.__class__.__name__,
            )
            return None

    async def replace(self, session_id: str, session_data: OidcSessionRecord) -> None:
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.redis.set(key, session_data.model_dump_json(), ex=self.session_ttl_seconds)

    async def delete(self, session_id: str) -> None:
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.redis.delete(key)

    async def set_ephemeral(self, key: str, value: str, ttl_seconds: int) -> None:
        redis_key = f"{OIDC_STATE_KEY_PREFIX}{key}"
        await self.redis.set(redis_key, value, ex=ttl_seconds)

    async def get_ephemeral(self, key: str) -> str | None:
        """Fetch and atomically delete an ephemeral key so state is single-use."""
        redis_key = f"{OIDC_STATE_KEY_PREFIX}{key}"
        raw = await self.redis.getdel(redis_key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)
