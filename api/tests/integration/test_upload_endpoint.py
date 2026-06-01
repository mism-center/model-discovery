import httpx
from fastapi.testclient import TestClient

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.clients.upload_client import UploadSession
from mismapi.core.deps import _get_upload_client
from mismapi.main import create_app
from tests.conftest import minimal_oidc_settings

TEST_RESOURCE_ID = "AbC123xYz890"
TEST_DATASET_RESOURCE_ID = "ds-uuid-9f87-4b2c-aaaa-1234567890ab"


async def _allow_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


class FakeUploadClient:
    def __init__(self) -> None:
        self.upload_part_calls: list[tuple[int, bytes]] = []
        self._failed_once = False
        self.completed = False
        self.init_resource_id: str | None = None

    async def init_upload(
        self,
        resource_id: str,
        filename: str,
        content_type: str | None,
    ) -> UploadSession:
        self.init_resource_id = resource_id
        assert filename == "dataset.bin"
        assert content_type == "application/octet-stream"
        return UploadSession(upload_id="upload-123", tracking_id="track-123")

    async def upload_part(self, upload_id: str, part_number: int, chunk: bytes) -> None:
        assert upload_id == "upload-123"
        self.upload_part_calls.append((part_number, chunk))
        if not self._failed_once:
            self._failed_once = True
            request = httpx.Request("POST", "http://upload-service/uploads/upload-123/parts")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("transient failure", request=request, response=response)

    async def complete_upload(self, upload_id: str, total_bytes: int, total_parts: int) -> None:
        assert upload_id == "upload-123"
        assert total_bytes == 24
        assert total_parts == 1
        self.completed = True

    async def close(self) -> None:
        return None


class MultiPartRetryUploadClient:
    def __init__(self) -> None:
        self.upload_part_calls: list[tuple[int, bytes]] = []
        self._failed_part_two_once = False
        self.completed = False
        self.init_resource_id: str | None = None

    async def init_upload(
        self,
        resource_id: str,
        filename: str,
        content_type: str | None,
    ) -> UploadSession:
        self.init_resource_id = resource_id
        assert filename == "dataset.bin"
        assert content_type == "application/octet-stream"
        return UploadSession(upload_id="upload-123", tracking_id="track-123")

    async def upload_part(self, upload_id: str, part_number: int, chunk: bytes) -> None:
        assert upload_id == "upload-123"
        self.upload_part_calls.append((part_number, chunk))
        if part_number == 2 and not self._failed_part_two_once:
            self._failed_part_two_once = True
            request = httpx.Request("POST", "http://upload-service/uploads/upload-123/parts")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("transient failure", request=request, response=response)

    async def complete_upload(self, upload_id: str, total_bytes: int, total_parts: int) -> None:
        assert upload_id == "upload-123"
        assert total_bytes == 8
        assert total_parts == 2
        self.completed = True

    async def close(self) -> None:
        return None


def test_upload_retries_chunk_after_transient_error() -> None:
    app = create_app(settings=minimal_oidc_settings())
    fake_upload_client = FakeUploadClient()
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_upload_client] = lambda: fake_upload_client

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/resources/{TEST_RESOURCE_ID}/files",
            files={
                "file": (
                    "dataset.bin",
                    b"0123456789ABCDEFGHIJKLMN",
                    "application/octet-stream",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["resource_id"] == TEST_RESOURCE_ID
    assert payload["upload_id"] == "upload-123"
    assert payload["tracking_id"] == "track-123"
    assert payload["parts_uploaded"] == 1
    assert fake_upload_client.completed is True
    assert fake_upload_client.init_resource_id == TEST_RESOURCE_ID
    assert len(fake_upload_client.upload_part_calls) >= 2


def test_upload_retry_retries_only_failing_part() -> None:
    app = create_app(settings=minimal_oidc_settings(UPLOAD_CHUNK_SIZE_BYTES=4))
    fake_upload_client = MultiPartRetryUploadClient()
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_upload_client] = lambda: fake_upload_client

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/resources/{TEST_RESOURCE_ID}/files",
            files={
                "file": (
                    "dataset.bin",
                    b"ABCDEFGH",
                    "application/octet-stream",
                )
            },
        )

    assert response.status_code == 200
    assert fake_upload_client.completed is True
    assert fake_upload_client.upload_part_calls == [
        (1, b"ABCD"),
        (2, b"EFGH"),
        (2, b"EFGH"),
    ]


def test_upload_accepts_dataset_uuid_resource_id() -> None:
    """Endpoint must accept any registry resource id, not just 12-char model ids.

    Registry uses UUIDs for datasets/tools — guard against any leftover
    ModelId regex constraint blocking those.
    """
    app = create_app(settings=minimal_oidc_settings())
    fake_upload_client = FakeUploadClient()
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_upload_client] = lambda: fake_upload_client

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/resources/{TEST_DATASET_RESOURCE_ID}/files",
            files={
                "file": (
                    "dataset.bin",
                    b"0123456789ABCDEFGHIJKLMN",
                    "application/octet-stream",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["resource_id"] == TEST_DATASET_RESOURCE_ID
    assert fake_upload_client.init_resource_id == TEST_DATASET_RESOURCE_ID


# NOTE: test_create_model_metadata and test_update_model_metadata were removed.
# POST /models now uses the registry (tested in test_search_endpoint.py / create endpoint tests).
# PUT /models/{id} was removed (registry uses immutable versioning).
