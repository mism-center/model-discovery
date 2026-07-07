"""Unit tests for `UploadSessionStoreService`.

These tests exercise the service against an in-memory fake Redis client that
implements just enough of the async API surface (`set`, `get`, `delete`) for
the token lifecycle paths under test. That keeps these tests as fast and
hermetic as the rest of the unit suite while still going through the real
serialization / key-naming code paths in the service.
"""

from __future__ import annotations

from typing import cast

import pytest
from redis.asyncio import Redis

from mismapi.core.errors import APIError
from mismapi.services.upload_session_store_service import (
    UPLOAD_TOKEN_KEY_PREFIX,
    UploadSessionStoreService,
)


class _InMemoryAsyncRedis:
    """Minimal async, in-memory stand-in for `redis.asyncio.Redis`.

    Only the methods exercised by the upload-token lifecycle are implemented.
    Values are stored as bytes to match the production client (which is
    constructed with `decode_responses=False`).
    """

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def set(
        self,
        key: str,
        value: str | bytes,
        ex: int | None = None,  # noqa: ARG002 - TTL not enforced in tests
        nx: bool = False,
    ) -> bool:
        if nx and key in self._data:
            return False
        self._data[key] = value.encode() if isinstance(value, str) else value
        return True

    async def get(self, key: str) -> bytes | None:
        return self._data.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                removed += 1
        return removed


def _make_service() -> tuple[UploadSessionStoreService, _InMemoryAsyncRedis]:
    fake_redis = _InMemoryAsyncRedis()
    service = UploadSessionStoreService(
        redis=cast(Redis, fake_redis),
        upload_token_ttl_seconds=900,
        tus_upload_ttl_seconds=3600,
    )
    return service, fake_redis


async def test_mint_then_consume_returns_claims_and_deletes_token() -> None:
    """A minted token can be consumed exactly once; the Redis key is removed
    as part of consumption so the token cannot be replayed.
    """
    service, fake_redis = _make_service()

    token = await service.mint_upload_token(
        user_id="user-1",
        max_bytes=1024,
        allowed_path="models/model-123/files",
    )
    assert f"{UPLOAD_TOKEN_KEY_PREFIX}{token}" in fake_redis._data

    claims = await service.consume_upload_token(token)

    assert claims.user_id == "user-1"
    assert claims.max_bytes == 1024
    assert claims.allowed_path == "models/model-123/files"
    # Consumption must atomically remove the key so the token is single-use.
    assert f"{UPLOAD_TOKEN_KEY_PREFIX}{token}" not in fake_redis._data


async def test_mint_consume_consume_rejects_second_consume() -> None:
    """The mint → consume → consume sequence must reject the second consume:
    upload tokens authorize exactly one tus `pre-create`, so a replay of the
    same token (e.g. by a malicious or buggy client) must surface as
    `auth_upload_token_invalid` (HTTP 401), not as a second successful claim.
    """
    service, _ = _make_service()

    token = await service.mint_upload_token(
        user_id="user-1",
        max_bytes=1024,
        allowed_path="models/model-123/files",
    )

    # First consume succeeds.
    await service.consume_upload_token(token)

    # Second consume must be rejected — the token was deleted on first use.
    with pytest.raises(APIError) as exc_info:
        await service.consume_upload_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "auth_upload_token_invalid"
