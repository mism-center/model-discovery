"""Tests for BioModelsClient.download_archive.

BioModels answers ``/model/download/{modelId}`` with a 302 to a versioned
``.omex`` path; the revision is only recoverable from that resolved URL.
Mocked with ``httpx.MockTransport``, matching test_cairns_enrichment.py.
"""

from __future__ import annotations

import io
import zipfile

import httpx
import pytest

from mismapi.clients.biomodels_client import BioModelsClient
from mismapi.core.errors import APIError

_BASE_URL = "https://biomodels.test"
_MODEL_ID = "BIOMD0000000732"
_DOWNLOAD_PATH = f"/model/download/{_MODEL_ID}"
# The path a live request for _MODEL_ID resolves to. Note the submission id
# differs from the model id, and the revision is its own path component.
_RESOLVED_PATH = "/services/download/get-files/MODEL1006230038/6/MODEL1006230038.6.omex"


def _zip_bytes(names: tuple[str, ...] = ("Kirschner_1998.xml",)) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, "<sbml/>")
    return buf.getvalue()


def _client(
    handler: httpx.MockTransport,
    *,
    max_archive_bytes: int = 100 * 1024 * 1024,
) -> BioModelsClient:
    client = BioModelsClient(
        base_url=_BASE_URL, timeout_seconds=5.0, max_archive_bytes=max_archive_bytes
    )
    client._client = httpx.AsyncClient(
        transport=handler,
        base_url=_BASE_URL,
        # download_archive reads the revision off the resolved URL, so the
        # redirect must actually be followed.
        follow_redirects=True,
    )
    return client


def _exploding_handler() -> httpx.MockTransport:
    def explode(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(f"unexpected request to {request.url}")

    return httpx.MockTransport(explode)


def _redirecting_handler(
    body: bytes,
    *,
    resolved_path: str = _RESOLVED_PATH,
    content_type: str = "application/zip",
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == _DOWNLOAD_PATH:
            return httpx.Response(302, headers={"Location": f"{_BASE_URL}{resolved_path}"})
        return httpx.Response(200, content=body, headers={"content-type": content_type})

    return httpx.MockTransport(handle)


# ── Happy path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_archive_revision_and_resolved_url() -> None:
    payload = _zip_bytes()
    archive = await _client(_redirecting_handler(payload)).download_archive(_MODEL_ID)

    assert archive.content == payload
    assert archive.revision == "6"
    assert archive.resolved_url == f"{_BASE_URL}{_RESOLVED_PATH}"
    assert zipfile.ZipFile(io.BytesIO(archive.content)).namelist() == ["Kirschner_1998.xml"]


@pytest.mark.asyncio
async def test_normalizes_lowercase_model_id() -> None:
    archive = await _client(_redirecting_handler(_zip_bytes())).download_archive("biomd0000000732")
    assert zipfile.is_zipfile(io.BytesIO(archive.content))


@pytest.mark.asyncio
async def test_revision_is_empty_when_url_does_not_match() -> None:
    handler = _redirecting_handler(_zip_bytes(), resolved_path="/files/archive.omex")
    archive = await _client(handler).download_archive(_MODEL_ID)
    assert archive.revision == ""


# ── Stubbed upstream ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stub_upstream_returns_a_zip_without_network() -> None:
    client = BioModelsClient(base_url=_BASE_URL, stub_upstream=True)
    client._client = httpx.AsyncClient(transport=_exploding_handler(), base_url=_BASE_URL)

    archive = await client.download_archive("biomd0000000732")

    assert archive.revision == "1"
    assert archive.resolved_url == f"stub://biomodels/{_MODEL_ID}"
    assert zipfile.ZipFile(io.BytesIO(archive.content)).namelist() == [
        f"{_MODEL_ID}.xml",
        "manifest.xml",
    ]


@pytest.mark.asyncio
async def test_stub_upstream_still_rejects_a_bad_model_id() -> None:
    client = BioModelsClient(base_url=_BASE_URL, stub_upstream=True)

    with pytest.raises(APIError) as exc:
        await client.download_archive("../../etc/passwd")

    assert exc.value.status_code == 400
    assert exc.value.code == "biomodels_invalid_model_id"


# ── Failure modes ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_model_id_makes_no_network_call() -> None:
    with pytest.raises(APIError) as exc:
        await _client(_exploding_handler()).download_archive("../../etc/passwd")

    assert exc.value.status_code == 400
    assert exc.value.code == "biomodels_invalid_model_id"


@pytest.mark.asyncio
async def test_unconfigured_base_url_makes_no_network_call() -> None:
    client = BioModelsClient(base_url="")
    client._client = httpx.AsyncClient(transport=_exploding_handler())

    with pytest.raises(APIError) as exc:
        await client.download_archive(_MODEL_ID)

    assert exc.value.status_code == 503
    assert exc.value.code == "biomodels_not_configured"


@pytest.mark.asyncio
async def test_upstream_404_is_model_not_found() -> None:
    handler = httpx.MockTransport(lambda _: httpx.Response(404, text="Not Found"))

    with pytest.raises(APIError) as exc:
        await _client(handler).download_archive(_MODEL_ID)

    assert exc.value.status_code == 404
    assert exc.value.code == "biomodels_model_not_found"


@pytest.mark.asyncio
async def test_upstream_500_is_download_failed() -> None:
    handler = httpx.MockTransport(lambda _: httpx.Response(500, text="boom"))

    with pytest.raises(APIError) as exc:
        await _client(handler).download_archive(_MODEL_ID)

    assert exc.value.status_code == 502
    assert exc.value.code == "biomodels_download_failed"


@pytest.mark.asyncio
async def test_html_login_page_answering_200_is_rejected() -> None:
    """An unknown path redirects to a login page that answers 200 with HTML."""
    handler = _redirecting_handler(
        b"<!doctype html><html><body>Sign in</body></html>",
        content_type="text/html",
    )

    with pytest.raises(APIError) as exc:
        await _client(handler).download_archive(_MODEL_ID)

    assert exc.value.status_code == 502
    assert exc.value.code == "biomodels_invalid_archive"


@pytest.mark.asyncio
async def test_archive_exceeding_cap_is_rejected() -> None:
    handler = _redirecting_handler(_zip_bytes(tuple(f"f{i}.xml" for i in range(50))))

    with pytest.raises(APIError) as exc:
        await _client(handler, max_archive_bytes=64).download_archive(_MODEL_ID)

    assert exc.value.status_code == 413
    assert exc.value.code == "biomodels_archive_too_large"


@pytest.mark.asyncio
async def test_timeout_is_surfaced_as_504() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(APIError) as exc:
        await _client(httpx.MockTransport(timeout)).download_archive(_MODEL_ID)

    assert exc.value.status_code == 504
    assert exc.value.code == "biomodels_download_timeout"


@pytest.mark.asyncio
async def test_transport_error_is_surfaced_as_502() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(APIError) as exc:
        await _client(httpx.MockTransport(refuse)).download_archive(_MODEL_ID)

    assert exc.value.status_code == 502
    assert exc.value.code == "biomodels_download_failed"
