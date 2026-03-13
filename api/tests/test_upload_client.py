import httpx

from clients.upload_client import UploadServiceClient
from core.errors import APIError


def _build_client_with_handler(
    handler: httpx.MockTransport,
) -> UploadServiceClient:
    client = UploadServiceClient(base_url="http://upload-service", timeout_seconds=5.0)
    client._client = httpx.AsyncClient(
        transport=handler,
        base_url="http://upload-service",
        timeout=5.0,
    )
    return client


async def test_init_upload_rejects_non_json_payload() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.init_upload(
                model_id="model-1",
                filename="file.bin",
                content_type="application/octet-stream",
            )
            raise AssertionError("Expected APIError for invalid JSON payload.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "upload_init_invalid"
    finally:
        await client.close()


async def test_init_upload_rejects_non_string_or_blank_ids() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"upload_id": None, "tracking_id": "   "})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.init_upload(
                model_id="model-1",
                filename="file.bin",
                content_type="application/octet-stream",
            )
            raise AssertionError("Expected APIError for invalid upload identifiers.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "upload_init_invalid"
    finally:
        await client.close()


async def test_init_upload_rejects_non_string_identifier_types() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"upload_id": 123, "tracking_id": {"id": "track-1"}})

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.init_upload(
                model_id="model-1",
                filename="file.bin",
                content_type="application/octet-stream",
            )
            raise AssertionError("Expected APIError for non-string upload identifiers.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "upload_init_invalid"
    finally:
        await client.close()


async def test_init_upload_rejects_malformed_json_shape() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["upload-1", "track-1"])

    client = _build_client_with_handler(httpx.MockTransport(handler))
    try:
        try:
            await client.init_upload(
                model_id="model-1",
                filename="file.bin",
                content_type="application/octet-stream",
            )
            raise AssertionError("Expected APIError for malformed init payload shape.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "upload_init_invalid"
    finally:
        await client.close()
