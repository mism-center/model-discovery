"""Integration tests for /resources/{id}/files and /resources/{id}/download."""

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mism_registry.enums import ResourceType, ResourceVersionStatus
from mism_registry.resource import Resource

from mismapi.auth.base import AuthenticatedPrincipal, require_principal
from mismapi.core.deps import _get_registry_service
from mismapi.core.errors import APIError
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService
from tests.conftest import minimal_oidc_settings


@pytest.fixture
def resource_dir(tmp_path: Path) -> Path:
    """A populated artifact directory with two files in nested layout."""
    base = tmp_path / "datasets" / "abc-123"
    base.mkdir(parents=True)
    (base / "results.json").write_text('{"foo": 1}')
    (base / "plots").mkdir()
    (base / "plots" / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)
    return base


def _make_resource(
    *, id: str = "ds-1", location_uri: str = "irods:///datasets/abc-123"
) -> Resource:
    return Resource(
        id=id,
        name="Example Dataset",
        resource_type=ResourceType.DATASET,
        location_uri=location_uri,
        description="Test dataset",
        version="1.0",
        version_status=ResourceVersionStatus.ACTIVE,
        owner="user-1",
        format_tags=["json"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


async def _allow_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="user-1",
        issuer="test",
        audience="mism-api",
        scopes=set(),
    )


def _make_app(service: RegistryService) -> TestClient:
    app = create_app(settings=minimal_oidc_settings())
    app.dependency_overrides[require_principal] = _allow_principal
    app.dependency_overrides[_get_registry_service] = lambda: service
    return TestClient(app)


# ── GET /resources/{id}/files ───────────────────────────────────


def test_list_files_returns_all_files_recursively(resource_dir: Path) -> None:
    resource = _make_resource()
    service = MagicMock(spec=RegistryService)
    service.find_resource_directory.return_value = (resource, resource_dir)

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/files")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resource_id"] == "ds-1"
    assert payload["location_uri"] == "irods:///datasets/abc-123"
    assert payload["total"] == 2

    paths = sorted(f["path"] for f in payload["files"])
    assert paths == ["plots/plot.png", "results.json"]

    # Each entry has the expected metadata shape.
    for f in payload["files"]:
        assert f["is_dir"] is False
        assert f["size_bytes"] >= 0
        assert f["modified_at"] is not None


def test_list_files_resource_missing_returns_404() -> None:
    service = MagicMock(spec=RegistryService)
    service.find_resource_directory.side_effect = APIError(
        status_code=404, code="not_found", detail="Resource 'missing' not found"
    )

    client = _make_app(service)
    response = client.get("/api/v1/resources/missing/files")

    assert response.status_code == 404


def test_list_files_unsupported_scheme_returns_400() -> None:
    service = MagicMock(spec=RegistryService)
    service.find_resource_directory.side_effect = APIError(
        status_code=400,
        code="unsupported_location_scheme",
        detail="Cannot serve files for scheme 's3'.",
    )

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/files")

    assert response.status_code == 400


# ── GET /resources/{id}/download (single file) ──────────────────


def test_download_single_file(resource_dir: Path) -> None:
    resource = _make_resource()
    service = MagicMock(spec=RegistryService)
    service.resolve_resource_file.return_value = (resource, resource_dir / "results.json")

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/download?file=results.json")

    assert response.status_code == 200
    assert response.content == b'{"foo": 1}'
    # FileResponse picks octet-stream when media_type is octet-stream
    assert response.headers["content-type"] == "application/octet-stream"
    # Filename should be the basename
    assert "results.json" in response.headers.get("content-disposition", "")

    service.resolve_resource_file.assert_called_once_with("ds-1", "results.json")


def test_download_single_file_traversal_blocked() -> None:
    service = MagicMock(spec=RegistryService)
    service.resolve_resource_file.side_effect = APIError(
        status_code=400,
        code="path_traversal_blocked",
        detail="File path escapes the resource directory.",
    )

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/download?file=../../etc/passwd")

    assert response.status_code == 400


def test_download_single_file_not_found_404() -> None:
    service = MagicMock(spec=RegistryService)
    service.resolve_resource_file.side_effect = APIError(
        status_code=404, code="file_not_found", detail="File 'missing.txt' not found"
    )

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/download?file=missing.txt")

    assert response.status_code == 404


# ── GET /resources/{id}/download (whole-dir zip) ────────────────


def test_download_zip_of_entire_directory(resource_dir: Path) -> None:
    resource = _make_resource()
    service = MagicMock(spec=RegistryService)
    service.get_resource_directory.return_value = (resource, resource_dir)

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="ds-1.zip"' in response.headers.get("content-disposition", "")

    # Validate the zip contains the expected files.
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = sorted(zf.namelist())
        # zipfile uses forward slashes regardless of OS
        assert names == ["plots/plot.png", "results.json"]
        with zf.open("results.json") as fh:
            assert fh.read() == b'{"foo": 1}'

    service.get_resource_directory.assert_called_once_with("ds-1")
    service.resolve_resource_file.assert_not_called()


def test_download_zip_resource_missing_returns_404() -> None:
    service = MagicMock(spec=RegistryService)
    service.get_resource_directory.side_effect = APIError(
        status_code=404, code="not_found", detail="Resource 'missing' not found"
    )

    client = _make_app(service)
    response = client.get("/api/v1/resources/missing/download")

    assert response.status_code == 404


def test_download_zip_streams_large_directory(tmp_path: Path) -> None:
    """A ~5 MiB directory zips and downloads correctly.

    We can't observe wire-level chunking through TestClient (it eagerly
    buffers the StreamingResponse body), so we assert the zip is valid and
    the contents round-trip. Streaming behavior itself is structural — see
    the ``_StreamingBuffer.seekable() -> False`` + ``ZipFile.open(...,
    force_zip64=True)`` pattern in resource_files.py.
    """
    big_dir = tmp_path / "datasets" / "big"
    big_dir.mkdir(parents=True)
    payload = b"A" * (5 * 1024 * 1024)  # 5 MiB
    (big_dir / "big.bin").write_bytes(payload)
    (big_dir / "small.txt").write_text("hello")

    resource = _make_resource(id="big-1", location_uri="irods:///datasets/big")
    service = MagicMock(spec=RegistryService)
    service.get_resource_directory.return_value = (resource, big_dir)

    client = _make_app(service)
    with client.stream("GET", "/api/v1/resources/big-1/download") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        body = b"".join(response.iter_bytes(chunk_size=64 * 1024))

    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        assert sorted(zf.namelist()) == ["big.bin", "small.txt"]
        with zf.open("big.bin") as fh:
            assert fh.read() == payload
        with zf.open("small.txt") as fh:
            assert fh.read() == b"hello"


def test_list_files_absent_directory_returns_empty_not_404() -> None:
    """A registered resource with nothing on the mount lists empty.

    This is what lets the detail page's Files section server-render: a 404 makes
    the React Query prefetch error, `dehydrate()` drops errored queries, and the
    browser has to refetch from scratch. Emptiness is a result, not a failure.
    """
    resource = _make_resource()
    service = MagicMock(spec=RegistryService)
    service.find_resource_directory.return_value = (resource, None)

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/files")

    assert response.status_code == 200
    payload = response.json()
    assert payload["files"] == []
    assert payload["total"] == 0
    assert payload["resource_id"] == "ds-1"


def test_download_still_404s_for_an_absent_directory() -> None:
    """Download keeps the strict accessor — there is genuinely nothing to send."""
    service = MagicMock(spec=RegistryService)
    service.get_resource_directory.side_effect = APIError(
        status_code=404,
        code="resource_files_not_found",
        detail="No files found on disk for resource at irods:///datasets/abc-123.",
    )

    client = _make_app(service)
    response = client.get("/api/v1/resources/ds-1/download")

    assert response.status_code == 404
