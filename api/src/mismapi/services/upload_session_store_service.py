import logging
import secrets
from dataclasses import dataclass

from pydantic import ValidationError
from redis.asyncio import Redis

from mismapi.core.errors import APIError
from mismapi.schemas.auth import TusUploadRecord, UploadTokenClaims

logger = logging.getLogger(__name__)

UPLOAD_TOKEN_KEY_PREFIX: str = "upload_token:"
TUS_UPLOAD_KEY_PREFIX: str = "tus_upload:"


@dataclass(slots=True)
class UploadSessionStoreService:
    """Redis-backed upload authorization state layered on top of the app session store."""

    redis: Redis
    upload_token_ttl_seconds: int
    tus_upload_ttl_seconds: int

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

    async def consume_upload_token(self, token: str) -> UploadTokenClaims:
        """
        Atomically read and delete claims for a minted upload token.

        Upload tokens authorize exactly one tus create request. Consuming the
        Redis key during `pre-create` prevents replaying a token to create
        multiple uploads for the same registry resource.
        """
        key = f"{UPLOAD_TOKEN_KEY_PREFIX}{token}"
        raw = await self.redis.get(key)
        if not raw:
            raise APIError(
                status_code=401,
                code="auth_upload_token_invalid",
                detail="Upload token is invalid or has expired",
            )
        try:
            claims = UploadTokenClaims.model_validate_json(raw)
            await self.redis.delete(key)
            return claims
        except (ValueError, ValidationError) as exc:
            logger.warning(
                "upload_token_invalid_payload token_prefix=%s error=%s",
                token[:8],
                exc.__class__.__name__,
            )
            raise APIError(
                status_code=401,
                code="auth_upload_token_invalid",
                detail="Upload token is invalid or has expired",
            ) from exc

    async def revoke_upload_token(self, token: str) -> None:
        """Best-effort delete after a successful tus upload (post-finish)."""
        key = f"{UPLOAD_TOKEN_KEY_PREFIX}{token}"
        await self.redis.delete(key)

    async def register_tus_upload(
        self,
        upload_id: str,
        *,
        user_id: str,
        resource_id: str,
    ) -> None:
        """Remember who authorized a tus upload ID during `pre-create`."""
        key = f"{TUS_UPLOAD_KEY_PREFIX}{upload_id}"
        record = TusUploadRecord(user_id=user_id, resource_id=resource_id)
        stored = await self.redis.set(
            key,
            record.model_dump_json(),
            ex=self.tus_upload_ttl_seconds,
            nx=True,
        )
        if not stored:
            raise APIError(
                status_code=409,
                code="tus_upload_id_collision",
                detail="Upload ID already exists. Please retry the upload.",
            )

    async def get_tus_upload(self, upload_id: str) -> TusUploadRecord | None:
        """Return the authorization context for a tus upload ID, if it exists."""
        key = f"{TUS_UPLOAD_KEY_PREFIX}{upload_id}"
        raw = await self.redis.get(key)
        if raw is None:
            return None
        try:
            return TusUploadRecord.model_validate_json(raw)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                "tus_upload_invalid_payload upload_id_prefix=%s error=%s",
                upload_id[:8],
                exc.__class__.__name__,
            )
            await self.redis.delete(key)
            return None

    async def delete_tus_upload(self, upload_id: str) -> None:
        """Delete the authorization context for a completed tus upload."""
        key = f"{TUS_UPLOAD_KEY_PREFIX}{upload_id}"
        await self.redis.delete(key)
