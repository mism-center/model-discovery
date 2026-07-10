"""Live end-to-end test for the model upload API (registry + tusd behind Docker).

Drives the full API surface of the upload feature against the running stack:

    initiate  -> POST /api/v1/models/{id}/upload  (mints upload token)
    upload    -> tus POST + PATCH to tusd          (fires pre-create + post-finish
                                                      hooks back to the API)
    verify    -> GET /api/v1/models/{id}           (upload_status == UPLOAD_COMPLETE)

Run after the stack is up:
    docker compose -f ../docker-compose.test.yaml up -d --build --wait
    uv run pytest tests/functional/test_upload_flow.py -m integration -v
"""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
import pytest

from tests.functional.helpers import unique_name

pytestmark = pytest.mark.integration

# tusd is published on the host alongside the api (see docker-compose.test.yaml).
TUSD_URL = "http://localhost:1080/files/"


def _encode_metadata(pairs: dict[str, str]) -> str:
    # tus Upload-Metadata: comma-separated "key base64(value)" pairs.
    return ",".join(f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in pairs.items())


def _tus_upload(token: str, resource_id: str, filename: str, data: bytes) -> None:
    """Create + transfer a tus upload in a single PATCH (small payload)."""
    with httpx.Client(timeout=30) as tus:
        create = tus.post(
            TUSD_URL,
            headers={
                "Tus-Resumable": "1.0.0",
                "Upload-Length": str(len(data)),
                "Upload-Metadata": _encode_metadata(
                    {"upload_token": token, "resource_id": resource_id, "filename": filename}
                ),
            },
        )
        # tusd in behind-proxy mode answers creation with 200 (not the bare-spec 201).
        assert create.status_code in (200, 201), create.text
        location = create.headers["Location"]

        patch = tus.patch(
            location,
            headers={
                "Tus-Resumable": "1.0.0",
                "Upload-Offset": "0",
                "Content-Type": "application/offset+octet-stream",
            },
            content=data,
        )
        assert patch.status_code == 204, patch.text
        assert patch.headers["Upload-Offset"] == str(len(data))


def _poll_model(
    api: httpx.Client, *, name: str, model_id: str, attempts: int = 25, delay: float = 0.2
) -> dict[str, Any]:
    """Return the model row once post-finish has stamped upload_status.

    No single-model GET route exists; read back via the list filter by name.
    Retries for ~attempts*delay seconds to let the async post-finish hook land.
    """
    match: dict[str, Any] = {"metadata": {}}
    for _ in range(attempts):
        r = api.get("/api/v1/models", params={"name": name})
        assert r.status_code == 200
        match = next((m for m in r.json()["results"] if m["id"] == model_id), match)
        if match["metadata"].get("upload_status") == "UPLOAD_COMPLETE":
            break
        time.sleep(delay)
    return match


def test_upload_flow_marks_model_complete(api: httpx.Client) -> None:
    name = unique_name("func-upload-flow")
    version = "1.0.0"
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "irods:///models/functional",
            "execution_type": "docker",
            "version": version,
        },
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    r = api.post(f"/api/v1/models/{model_id}/upload")
    assert r.status_code == 200
    token = r.json()["token"]

    _tus_upload(token, model_id, "model.bin", b"hello-mism-upload")

    # tusd fires post-finish as an async server-to-server hook and does NOT
    # block the client's final PATCH on it, so the stamp can land shortly after
    # the upload returns. Poll the readback instead of reading once (which races
    # the hook and flakes under load).
    match = _poll_model(api, name=name, model_id=model_id)
    assert match["metadata"].get("upload_status") == "UPLOAD_COMPLETE", match["metadata"]
    # post-finish reconciles location_uri to the <resource_id>/<version> dir.
    assert match["location_uri"] == f"{model_id}/{version}"


def test_upload_rejected_with_bad_token(api: httpx.Client) -> None:
    name = unique_name("func-upload-badtoken")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "irods:///models/functional",
            "execution_type": "docker",
        },
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    # pre-create hook must reject: tusd surfaces the rejection as a 4xx on create.
    with httpx.Client(timeout=30) as tus:
        create = tus.post(
            TUSD_URL,
            headers={
                "Tus-Resumable": "1.0.0",
                "Upload-Length": "5",
                "Upload-Metadata": _encode_metadata(
                    {"upload_token": "bogus", "resource_id": model_id, "filename": "x.bin"}
                ),
            },
        )
        assert create.status_code >= 400
