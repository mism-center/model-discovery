import httpx
from fastapi.testclient import TestClient

from auth.base import AuthenticatedPrincipal, require_principal
from clients.upload_client import ModelMetadataUpsertResult, UploadSession
from main import create_app

TEST_MODEL_ID = 'AbC123xYz890'
CREATED_MODEL_ID = 'Cr8ModelID12'


class FakeUploadClient:
    def __init__(self) -> None:
        self.upload_part_calls: list[tuple[int, bytes]] = []
        self._failed_once = False
        self.completed = False
        self.created_payload: dict[str, object] | None = None
        self.updated_payload: dict[str, object] | None = None

    async def create_model(
        self,
        name: str,
        description: str | None,
        version: str | None,
        metadata: dict[str, str | int | float | bool | None],
    ) -> ModelMetadataUpsertResult:
        self.created_payload = {
            "name": name,
            "description": description,
            "version": version,
            "metadata": metadata,
        }
        return ModelMetadataUpsertResult(model_id=CREATED_MODEL_ID, tracking_id="track-created-1")

    async def update_model(
        self,
        model_id: str,
        name: str,
        description: str | None,
        version: str | None,
        metadata: dict[str, str | int | float | bool | None],
    ) -> ModelMetadataUpsertResult:
        self.updated_payload = {
            "model_id": model_id,
            "name": name,
            "description": description,
            "version": version,
            "metadata": metadata,
        }
        return ModelMetadataUpsertResult(model_id=model_id, tracking_id="track-updated-1")

    async def init_upload(
        self,
        model_id: str,
        filename: str,
        content_type: str | None,
    ) -> UploadSession:
        assert model_id == TEST_MODEL_ID
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

    async def init_upload(
        self,
        model_id: str,
        filename: str,
        content_type: str | None,
    ) -> UploadSession:
        assert model_id == TEST_MODEL_ID
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


async def allow_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def test_upload_retries_chunk_after_transient_error() -> None:
    app = create_app()
    app.dependency_overrides[require_principal] = allow_principal
    fake_upload_client = FakeUploadClient()

    with TestClient(app) as client:
        app.state.upload_client = fake_upload_client
        response = client.post(
            f"/api/v1/models/{TEST_MODEL_ID}/files",
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
        assert payload["model_id"] == TEST_MODEL_ID
        assert payload["upload_id"] == "upload-123"
        assert payload["tracking_id"] == "track-123"
        assert payload["parts_uploaded"] == 1
        assert fake_upload_client.completed is True
        assert len(fake_upload_client.upload_part_calls) >= 2


def test_upload_retry_retries_only_failing_part() -> None:
    app = create_app()
    app.dependency_overrides[require_principal] = allow_principal
    fake_upload_client = MultiPartRetryUploadClient()

    with TestClient(app) as client:
        app.state.upload_client = fake_upload_client
        app.state.settings.upload_chunk_size_bytes = 4
        response = client.post(
            f"/api/v1/models/{TEST_MODEL_ID}/files",
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


def test_create_model_metadata() -> None:
    app = create_app()
    app.dependency_overrides[require_principal] = allow_principal
    fake_upload_client = FakeUploadClient()

    with TestClient(app) as client:
        app.state.upload_client = fake_upload_client
        response = client.post(
            "/api/v1/models",
            json={
                "name": "example-model",
                "description": "An example model",
                "version": "1.0.0",
                "metadata": {"framework": "pytorch"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "accepted"
        assert payload["model_id"] == CREATED_MODEL_ID
        assert payload["tracking_id"] == "track-created-1"
        assert fake_upload_client.created_payload is not None


def test_update_model_metadata() -> None:
    app = create_app()
    app.dependency_overrides[require_principal] = allow_principal
    fake_upload_client = FakeUploadClient()

    with TestClient(app) as client:
        app.state.upload_client = fake_upload_client
        response = client.put(
            f"/api/v1/models/{TEST_MODEL_ID}",
            json={
                "name": "example-model",
                "description": "An updated model",
                "version": "1.0.1",
                "metadata": {"framework": "pytorch", "quantized": False},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "accepted"
        assert payload["model_id"] == TEST_MODEL_ID
        assert payload["tracking_id"] == "track-updated-1"
        assert fake_upload_client.updated_payload is not None
