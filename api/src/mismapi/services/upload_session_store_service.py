import logging
import secrets
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, cast

from pydantic import ValidationError
from redis.asyncio import Redis

from mismapi.core.errors import APIError
from mismapi.schemas.auth import TusUploadRecord, UploadTokenClaims

logger = logging.getLogger(__name__)

UPLOAD_TOKEN_KEY_PREFIX: str = "upload_token:"
TUS_UPLOAD_KEY_PREFIX: str = "tus_upload:"
TUS_FILENAME_LOCK_KEY_PREFIX: str = "tus_filename_lock:"

# Compare-and-swap release: only delete the lock if its current value matches the caller's
# owner token. Prevents a stale post-finish / pre-terminate from releasing a
# lock that a later upload re-acquired after the original lock TTL'd out.
_RELEASE_FILENAME_LOCK_LUA: str = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


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

    async def register_upload(
        self,
        upload_id: str,
        *,
        user_id: str,
        resource_id: str,
        filename: str,
    ) -> None:
        """
        Remember who authorized a tus upload ID during `pre-create`.

        `filename` is stored alongside ownership so `post-finish` and
        `pre-terminate` can release the corresponding `(resource_id, filename)`
        lock without having to re-derive it from hook metadata (which the
        client controls).
        """
        key = f"{TUS_UPLOAD_KEY_PREFIX}{upload_id}"
        record = TusUploadRecord(
            user_id=user_id,
            resource_id=resource_id,
            filename=filename,
        )
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

    async def get_upload_session(self, upload_id: str) -> TusUploadRecord | None:
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

    async def delete_upload_session(self, upload_id: str) -> None:
        """Delete the authorization context for a completed tus upload."""
        key = f"{TUS_UPLOAD_KEY_PREFIX}{upload_id}"
        await self.redis.delete(key)

    @staticmethod
    def _filename_lock_key(resource_id: str, filename: str) -> str:
        return f"{TUS_FILENAME_LOCK_KEY_PREFIX}{resource_id}:{filename}"

    async def try_lock_filename(
        self,
        *,
        resource_id: str,
        filename: str,
        owner: str,
    ) -> bool:
        """Atomically claim `(resource_id, filename)` for the calling upload.

        Returns True if the lock was acquired, False if another in-flight upload
        already holds it. The check-and-set is a single Redis `SET NX EX`, so it
        closes the TOCTOU window between the existence check on disk and tusd
        writing the file: two concurrent `pre-create` hooks for the same target
        path cannot both succeed.

        `owner` must be a value unique to this upload (the synthesized tus
        upload ID). `release_filename_lock` uses it as a CAS token so we never
        release a lock that a later upload reclaimed after a TTL expiry.

        TTL matches `tus_upload_ttl_seconds` so an abandoned upload (client
        crashes, no `pre-terminate` ever fires) eventually frees the slot.
        """
        key = self._filename_lock_key(resource_id, filename)
        acquired = await self.redis.set(
            key,
            owner,
            ex=self.tus_upload_ttl_seconds,
            nx=True,
        )
        return bool(acquired)

    async def release_filename_lock(
        self,
        *,
        resource_id: str,
        filename: str,
        owner: str,
    ) -> None:
        """
        Best-effort CAS release of the `(resource_id, filename)` lock.

        No-op if the lock has already expired or been reclaimed by another
        upload (i.e. its current value no longer matches `owner`). Safe to call
        from any post-acquisition failure path and from `post-finish` /
        `pre-terminate`.
        """
        key = self._filename_lock_key(resource_id, filename)
        # redis-py types `Redis.eval` as a sync/async union, but our client is
        # async (redis.asyncio.Redis); cast to the awaitable arm so pyright
        # accepts the await.
        await cast(
            Awaitable[Any],
            self.redis.eval(_RELEASE_FILENAME_LOCK_LUA, 1, key, owner),  # pyright: ignore[reportUnknownMemberType]
        )
