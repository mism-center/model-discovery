"""Live tests for dataset CRUD (registry + DB behind Docker)."""

from __future__ import annotations

import httpx
import pytest

from tests.functional.helpers import unique_name

pytestmark = pytest.mark.integration


def test_create_and_list_dataset(api: httpx.Client) -> None:
    name = unique_name("func-dataset")
    r = api.post(
        "/api/v1/datasets",
        json={
            "name": name,
            "location_uri": "irods:///datasets/functional",
            "format_tags": ["csv"],
            "description": "functional test dataset",
        },
    )
    assert r.status_code == 201
    dataset = r.json()
    assert dataset["name"] == name
    assert dataset["id"]
    assert "csv" in dataset["format_tags"]

    r = api.get("/api/v1/datasets", params={"name": name})
    assert r.status_code == 200
    payload = r.json()
    assert len(payload["results"]) >= 1
    ids = [item["id"] for item in payload["results"]]
    assert dataset["id"] in ids


def test_update_dataset(api: httpx.Client) -> None:
    name = unique_name("func-dataset-upd")
    r = api.post(
        "/api/v1/datasets",
        json={
            "name": name,
            "location_uri": "irods:///datasets/functional",
        },
    )
    assert r.status_code == 201
    dataset_id = r.json()["id"]

    r = api.put(
        f"/api/v1/datasets/{dataset_id}",
        json={"description": "updated via functional test", "format_tags": ["parquet"]},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "updated via functional test"


def test_create_dataset_missing_fields_returns_400(api: httpx.Client) -> None:
    r = api.post("/api/v1/datasets", json={"description": "no name or uri"})
    assert r.status_code == 400
