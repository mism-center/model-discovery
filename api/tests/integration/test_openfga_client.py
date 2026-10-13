import json

import httpx

from mismapi.clients.openfga_client import OpenFGAClient
from mismapi.core.errors import APIError


def _build_client_with_handler(
    handler: httpx.MockTransport,
    store_id: str = "test-store",
    authorization_model_id: str = "",
) -> OpenFGAClient:
    client = OpenFGAClient(
        base_url="http://openfga",
        store_id=store_id,
        authorization_model_id=authorization_model_id,
        timeout_seconds=5.0,
    )
    client._client = httpx.AsyncClient(
        transport=handler,
        base_url="http://openfga",
        timeout=5.0,
    )
    return client


async def test_check_allowed_true() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores/test-store/check"
        return httpx.Response(200, json={"allowed": True})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        allowed = await client.check(
            user="user:alice", relation="uploader", object_="platform:main"
        )
        assert allowed is True
    finally:
        await client.close()


async def test_check_allowed_false() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"allowed": False})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        allowed = await client.check(user="user:bob", relation="uploader", object_="platform:main")
        assert allowed is False
    finally:
        await client.close()


async def test_check_sends_tuple_key_body() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores/test-store/check"
        captured["body"] = request.content
        return httpx.Response(200, json={"allowed": True})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        await client.check(user="user:alice", relation="image_checker", object_="platform:main")
        body = json.loads(captured["body"])  # type: ignore[arg-type]
        assert body["tuple_key"] == {
            "user": "user:alice",
            "relation": "image_checker",
            "object": "platform:main",
        }
        assert "authorization_model_id" not in body
    finally:
        await client.close()


async def test_check_includes_authorization_model_id_when_set() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"allowed": True})

    client = _build_client_with_handler(
        httpx.MockTransport(handler), authorization_model_id="model-123"
    )
    try:
        await client.check(user="user:alice", relation="uploader", object_="platform:main")
        body = json.loads(captured["body"])  # type: ignore[arg-type]
        assert body["authorization_model_id"] == "model-123"
    finally:
        await client.close()


async def test_check_missing_allowed_field_raises() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.check(user="user:alice", relation="uploader", object_="platform:main")
            raise AssertionError("Expected APIError for malformed check response.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "openfga_check_invalid_response"
    finally:
        await client.close()


async def test_check_5xx_raises_502() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"code": "internal_error", "message": "store unavailable"})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.check(user="user:alice", relation="uploader", object_="platform:main")
            raise AssertionError("Expected APIError for 5xx.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "openfga_check_failed"
    finally:
        await client.close()


async def test_check_4xx_passthrough_with_message() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"code": "validation_error", "message": "invalid tuple_key"}
        )

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.check(user="user:alice", relation="uploader", object_="platform:main")
            raise AssertionError("Expected APIError for 4xx.")
        except APIError as exc:
            assert exc.status_code == 400
            assert exc.detail == "invalid tuple_key"
    finally:
        await client.close()


async def test_write_tuple_sends_writes_body() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stores/test-store/write"
        captured["body"] = request.content
        return httpx.Response(200, json={})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        await client.write_tuple(user="user:alice", relation="owner", object_="model:m1")
        body = json.loads(captured["body"])  # type: ignore[arg-type]
        assert body["writes"]["tuple_keys"] == [
            {"user": "user:alice", "relation": "owner", "object": "model:m1"}
        ]
        assert "deletes" not in body
    finally:
        await client.close()


async def test_delete_tuple_sends_deletes_body() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        await client.delete_tuple(user="user:dana", relation="uploader", object_="platform:main")
        body = json.loads(captured["body"])  # type: ignore[arg-type]
        assert body["deletes"]["tuple_keys"] == [
            {"user": "user:dana", "relation": "uploader", "object": "platform:main"}
        ]
        assert "writes" not in body
    finally:
        await client.close()


async def test_write_timeout_raises_504() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("boom")

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.write_tuple(user="user:alice", relation="owner", object_="model:m1")
            raise AssertionError("Expected APIError for timeout.")
        except APIError as exc:
            assert exc.status_code == 504
            assert exc.code == "openfga_write_timeout"
    finally:
        await client.close()
