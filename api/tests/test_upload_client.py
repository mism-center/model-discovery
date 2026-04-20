import httpx
import respx

from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.errors import APIError

UPLOAD_BASE_URL = "http://upload-service"
INIT_URL = f"{UPLOAD_BASE_URL}/models/model-1/files/init"
MODELS_URL = f"{UPLOAD_BASE_URL}/models"


def _build_client() -> UploadServiceClient:
    return UploadServiceClient(base_url=UPLOAD_BASE_URL, timeout_seconds=5.0)


@respx.mock
async def test_init_upload_rejects_non_json_payload() -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, text="not-json"))

    client = _build_client()
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


@respx.mock
async def test_init_upload_rejects_non_string_or_blank_ids() -> None:
    respx.post(INIT_URL).mock(
        return_value=httpx.Response(200, json={"upload_id": None, "tracking_id": "   "})
    )

    client = _build_client()
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


@respx.mock
async def test_init_upload_rejects_non_string_identifier_types() -> None:
    respx.post(INIT_URL).mock(
        return_value=httpx.Response(200, json={"upload_id": 123, "tracking_id": {"id": "track-1"}})
    )

    client = _build_client()
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


@respx.mock
async def test_create_model_passthrough_409_conflict() -> None:
    respx.post(MODELS_URL).mock(
        return_value=httpx.Response(
            409,
            json={
                "error": {
                    "code": "model_already_exists",
                    "detail": "Model with this ID already exists.",
                }
            },
        )
    )

    client = _build_client()
    try:
        try:
            await client.create_model(
                name="test-model",
                description=None,
                version=None,
                metadata={},
            )
            raise AssertionError("Expected APIError for 409 conflict.")
        except APIError as exc:
            assert exc.status_code == 409
            assert exc.code == "model_already_exists"
            assert exc.detail == "Model with this ID already exists."
    finally:
        await client.close()


@respx.mock
async def test_create_model_passthrough_5xx_as_502() -> None:
    respx.post(MODELS_URL).mock(
        return_value=httpx.Response(503, json={"error": {"detail": "Service unavailable"}})
    )

    client = _build_client()
    try:
        try:
            await client.create_model(
                name="test-model",
                description=None,
                version=None,
                metadata={},
            )
            raise AssertionError("Expected APIError for 5xx.")
        except APIError as exc:
            assert exc.status_code == 502
            assert exc.code == "model_upsert_failed"
    finally:
        await client.close()


@respx.mock
async def test_init_upload_rejects_malformed_json_shape() -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=["upload-1", "track-1"]))

    client = _build_client()
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
