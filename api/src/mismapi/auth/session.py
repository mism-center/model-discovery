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


SESSION_KEY_PREFIX: str = "session:"


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
