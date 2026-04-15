import json
import secrets
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


class SessionStore(Protocol):
    async def create(self, session_data: dict[str, str]) -> str: ...

    async def get(self, session_id: str) -> dict[str, str] | None: ...

    async def replace(self, session_id: str, session_data: dict[str, str]) -> None: ...

    async def delete(self, session_id: str) -> None: ...

    async def set_ephemeral(self, key: str, value: str, ttl_seconds: int) -> None: ...

    async def get_ephemeral(self, key: str) -> str | None: ...


SESSION_KEY_PREFIX = "session:"
OIDC_STATE_KEY_PREFIX = "oidc_state:"


@dataclass(slots=True)
class RedisSessionStore:
    redis: Redis
    session_ttl_seconds: int

    async def create(self, session_data: dict[str, str]) -> str:
        session_id = secrets.token_urlsafe(32)
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.redis.set(key, json.dumps(session_data), ex=self.session_ttl_seconds)
        return session_id

    async def get(self, session_id: str) -> dict[str, str] | None:
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        raw = await self.redis.get(key)
        if raw is None:
            return None
        payload: dict[str, str] = json.loads(raw)
        return payload

    async def replace(self, session_id: str, session_data: dict[str, str]) -> None:
        key = f"{SESSION_KEY_PREFIX}{session_id}"
        await self.redis.set(key, json.dumps(session_data), ex=self.session_ttl_seconds)

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
