"""Integration tests that hit the real API running in Docker.

Run with:
    docker compose -f docker-compose.test.yaml up -d --build --wait
    uv run pytest tests/test_integration.py -m integration -v
    docker compose -f docker-compose.test.yaml down -v
"""

import os
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("INTEGRATION_TEST_BASE_URL", "http://localhost:8000")

pytestmark = pytest.mark.integration


@pytest.fixture()
def api() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        yield client


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ── Health ───────────────────────────────────────────────────────


def test_healthz(api: httpx.Client) -> None:
    r = api.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Models ───────────────────────────────────────────────────────


def test_create_and_list_model(api: httpx.Client) -> None:
    name = _unique("int-model")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "https://example.com/model",
            "execution_type": "DOCKER",
            "description": "integration test model",
        },
    )
    assert r.status_code == 201
    model = r.json()
    assert model["name"] == name
    assert model["id"]

    # List and find it
    r = api.get("/api/v1/models", params={"name": name})
    assert r.status_code == 200
    payload = r.json()
    assert payload["total"] >= 1
    ids = [item["id"] for item in payload["results"]]
    assert model["id"] in ids


def test_create_model_and_run(api: httpx.Client) -> None:
    name = _unique("int-model-run")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "https://example.com/model",
            "execution_type": "DOCKER",
        },
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    # Create a run
    r = api.post(f"/api/v1/models/{model_id}/runs", json={})
    assert r.status_code == 201
    run = r.json()
    assert run["model_id"] == model_id
    assert run["status"]


def test_update_model(api: httpx.Client) -> None:
    name = _unique("int-model-upd")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "https://example.com/model",
            "execution_type": "DOCKER",
        },
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    # Update
    r = api.put(
        f"/api/v1/models/{model_id}",
        json={"description": "updated via integration test", "version": "2.0"},
    )
    assert r.status_code == 200
    assert r.json()["version"] == "2.0"


def test_create_model_missing_fields_returns_422(api: httpx.Client) -> None:
    r = api.post("/api/v1/models", json={"name": "incomplete"})
    assert r.status_code == 422


# ── Datasets ─────────────────────────────────────────────────────


def test_create_and_list_dataset(api: httpx.Client) -> None:
    name = _unique("int-dataset")
    r = api.post(
        "/api/v1/datasets",
        json={
            "name": name,
            "location_uri": "s3://bucket/data.csv",
            "format_tags": ["csv"],
            "description": "integration test dataset",
        },
    )
    assert r.status_code == 201
    dataset = r.json()
    assert dataset["name"] == name
    assert dataset["id"]
    assert "csv" in dataset["format_tags"]

    # List and find it
    r = api.get("/api/v1/datasets", params={"name": name})
    assert r.status_code == 200
    payload = r.json()
    assert payload["total"] >= 1
    ids = [item["id"] for item in payload["results"]]
    assert dataset["id"] in ids


def test_update_dataset(api: httpx.Client) -> None:
    name = _unique("int-dataset-upd")
    r = api.post(
        "/api/v1/datasets",
        json={
            "name": name,
            "location_uri": "s3://bucket/data.csv",
        },
    )
    assert r.status_code == 201
    dataset_id = r.json()["id"]

    r = api.put(
        f"/api/v1/datasets/{dataset_id}",
        json={"description": "updated via integration test", "format_tags": ["parquet"]},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "updated via integration test"


def test_create_dataset_missing_fields_returns_422(api: httpx.Client) -> None:
    r = api.post("/api/v1/datasets", json={"description": "no name or uri"})
    assert r.status_code == 422
