"""Live tests for model CRUD and runs (registry + DB behind Docker)."""

from __future__ import annotations

import httpx
import pytest

from tests.functional.helpers import unique_name

pytestmark = pytest.mark.integration


def test_create_and_list_model(api: httpx.Client) -> None:
    name = unique_name("func-model")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "https://example.com/model",
            "execution_type": "docker",
            "description": "functional test model",
        },
    )
    assert r.status_code == 201
    model = r.json()
    assert model["name"] == name
    assert model["id"]

    r = api.get("/api/v1/models", params={"name": name})
    assert r.status_code == 200
    payload = r.json()
    assert len(payload["results"]) >= 1
    ids = [item["id"] for item in payload["results"]]
    assert model["id"] in ids


def test_create_model_and_run(api: httpx.Client) -> None:
    name = unique_name("int-model-run")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "https://example.com/model",
            "execution_type": "docker",
        },
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    r = api.post(f"/api/v1/models/{model_id}/runs", json={})
    assert r.status_code == 201
    run = r.json()
    assert run["model_id"] == model_id
    assert run["status"]


def test_update_model(api: httpx.Client) -> None:
    name = unique_name("func-model-upd")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "https://example.com/model",
            "execution_type": "docker",
        },
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    r = api.put(
        f"/api/v1/models/{model_id}",
        json={"description": "updated via functional test", "version": "2.0"},
    )
    assert r.status_code == 200
    assert r.json()["version"] == "2.0"


def test_create_model_missing_fields_returns_400(api: httpx.Client) -> None:
    r = api.post("/api/v1/models", json={"name": "incomplete"})
    assert r.status_code == 400
