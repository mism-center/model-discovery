import logging
import secrets
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError
from redis.asyncio import Redis

from mismapi.core.errors import APIError
from mismapi.schemas.auth import OidcSessionRecord, UploadTokenClaims

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    async def create(self, session_data: OidcSessionRecord) -> str: ...

    async def get(self, session_id: str) -> OidcSessionRecord | None: ...

    async def replace(self, session_id: str, session_data: OidcSessionRecord) -> None: ...

    async def delete(self, session_id: str) -> None: ...

    async def mint_upload_token(self, user_id: str, max_bytes: int, allowed_path: str) -> str: ...

    async def validate_upload_token(self, token: str) -> UploadTokenClaims: ...

    async def revoke_upload_token(self, token: str) -> None: ...


UPLOAD_TOKEN_KEY_PREFIX: str = "upload_token:"
SESSION_KEY_PREFIX: str = "session:"


@dataclass(slots=True)
class RedisSessionStore:
    redis: Redis
    session_ttl_seconds: int
    upload_token_ttl_seconds: int

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

    async def mint_upload_token(
        self,
        user_id: str,
        max_bytes: int,
        allowed_path: str,
    ) -> str:
        token = secrets.token_urlsafe(32)
        claims = UploadTokenClaims(
            user_id=user_id,
            max_bytes=max_bytes,
            allowed_path=allowed_path,
        )
        await self.redis.set(
            f"{UPLOAD_TOKEN_KEY_PREFIX}{token}",
            claims.model_dump_json(),
            ex=self.upload_token_ttl_seconds,
        )
        return token

    async def validate_upload_token(self, token: str) -> UploadTokenClaims:
        """
        Read claims for a minted upload token without removing the key.

        The entry still expires at Redis TTL (`upload_token_ttl_seconds` at
        mint time). `revoke_upload_token` removes it early after a successful
        tus completion when tusd forwards `upload_token` in `post-finish`
        metadata.
        """
        key = f"{UPLOAD_TOKEN_KEY_PREFIX}{token}"
        raw = await self.redis.get(key)
        if not raw:
            raise APIError(
                status_code=401,
                code="auth_upload_token_invalid",
                detail="Upload token is invalid or has expired",
            )
        return UploadTokenClaims.model_validate_json(raw)

    async def revoke_upload_token(self, token: str) -> None:
        """Best-effort delete after a successful tus upload (post-finish)."""
        key = f"{UPLOAD_TOKEN_KEY_PREFIX}{token}"
        await self.redis.delete(key)
