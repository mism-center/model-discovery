"""Integration tests that hit the real API running in Docker.

Run with:
    docker compose -f docker-compose.test.yaml up -d --build --wait
    uv run pytest tests/test_integration.py -m integration -v
    docker compose -f docker-compose.test.yaml down -v
"""

import os
import uuid
from collections.abc import Generator

import httpx
import pytest

BASE_URL = os.environ.get("INTEGRATION_TEST_BASE_URL", "http://localhost:8000")

pytestmark = pytest.mark.integration


@pytest.fixture()
def api() -> Generator[httpx.Client, None, None]:
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
            "execution_type": "docker",
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
            "execution_type": "docker",
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
            "execution_type": "docker",
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


# ── Search ──────────────────────────────────────────────────────


def _seed_search_fixtures(api: httpx.Client) -> dict[str, str]:
    """Create a model and a dataset with unique names, return their ids and names."""
    tag = uuid.uuid4().hex[:8]

    r = api.post(
        "/api/v1/models",
        json={
            "name": f"Cardiac Simulator {tag}",
            "location_uri": "https://example.com/cardiac",
            "execution_type": "docker",
            "description": "A computational model for cardiac tissue electrophysiology",
            "owner": f"owner-{tag}",
        },
    )
    assert r.status_code == 201
    model = r.json()

    r = api.post(
        "/api/v1/datasets",
        json={
            "name": f"ECG Signal Dataset {tag}",
            "location_uri": "https://example.com/ecg",
            "description": "Electrocardiogram signals from cardiac patients",
            "owner": f"owner-{tag}",
            "format_tags": ["csv", "hdf5"],
        },
    )
    assert r.status_code == 201
    dataset = r.json()

    r = api.post(
        "/api/v1/models",
        json={
            "name": f"Neural Classifier {tag}",
            "location_uri": "https://example.com/nn",
            "execution_type": "python",
            "description": "Deep learning classifier for brain MRI images",
            "owner": f"other-{tag}",
        },
    )
    assert r.status_code == 201
    nn_model = r.json()

    return {
        "tag": tag,
        "model_id": model["id"],
        "dataset_id": dataset["id"],
        "nn_model_id": nn_model["id"],
        "owner": f"owner-{tag}",
        "other_owner": f"other-{tag}",
    }


def test_search_no_query_returns_all(api: httpx.Client) -> None:
    """POST /search with no query returns results sorted by created_at desc."""
    r = api.post("/api/v1/search", json={})
    assert r.status_code == 200
    payload = r.json()
    assert payload["total"] >= 0
    assert "results" in payload
    assert "aggs" in payload


def test_search_full_text_query(api: httpx.Client) -> None:
    """Full-text search returns matching resources ranked by relevance."""
    fixtures = _seed_search_fixtures(api)
    tag = fixtures["tag"]

    r = api.post("/api/v1/search", json={"query": f"cardiac {tag}"})
    assert r.status_code == 200
    payload = r.json()

    assert payload["total"] >= 2
    # Both "Cardiac Simulator" (name match) and "ECG Signal Dataset"
    # (description match) should appear
    ids = [item["id"] for item in payload["results"]]
    assert fixtures["model_id"] in ids
    assert fixtures["dataset_id"] in ids

    # All results should have a score
    for item in payload["results"]:
        assert item["score"] is not None
        assert item["score"] > 0


def test_search_full_text_relevance_ranking(api: httpx.Client) -> None:
    """Name matches (weight A) should score higher than description matches (weight B)."""
    fixtures = _seed_search_fixtures(api)
    tag = fixtures["tag"]

    r = api.post("/api/v1/search", json={"query": f"cardiac {tag}"})
    assert r.status_code == 200
    results = r.json()["results"]

    # Find the two fixtures in results
    model_score = next(
        (item["score"] for item in results if item["id"] == fixtures["model_id"]),
        None,
    )
    dataset_score = next(
        (item["score"] for item in results if item["id"] == fixtures["dataset_id"]),
        None,
    )
    assert model_score is not None and dataset_score is not None
    # "Cardiac" in name (weight A) should rank higher than "cardiac" in description (weight B)
    assert model_score > dataset_score


def test_search_filter_by_resource_type(api: httpx.Client) -> None:
    """Filtering by resource_type narrows results."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={
            "filters": [
                {"field": "resource_type", "op": "eq", "value": "dataset"},
                {"field": "owner", "op": "eq", "value": fixtures["owner"]},
            ]
        },
    )
    assert r.status_code == 200
    payload = r.json()

    for item in payload["results"]:
        assert item["resource_type"] == "dataset"
    ids = [item["id"] for item in payload["results"]]
    assert fixtures["dataset_id"] in ids
    assert fixtures["model_id"] not in ids


def test_search_filter_by_owner(api: httpx.Client) -> None:
    """Filtering by owner returns only that owner's resources."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={"filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}]},
    )
    assert r.status_code == 200
    payload = r.json()

    for item in payload["results"]:
        assert item["owner"] == fixtures["owner"]
    # nn_model belongs to other_owner, should not appear
    ids = [item["id"] for item in payload["results"]]
    assert fixtures["nn_model_id"] not in ids


def test_search_filter_by_execution_type(api: httpx.Client) -> None:
    """Filtering by execution_type works for enum fields."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={
            "filters": [
                {"field": "execution_type", "op": "eq", "value": "python"},
                {"field": "owner", "op": "eq", "value": fixtures["other_owner"]},
            ]
        },
    )
    assert r.status_code == 200
    payload = r.json()

    ids = [item["id"] for item in payload["results"]]
    assert fixtures["nn_model_id"] in ids
    for item in payload["results"]:
        assert item["execution_type"] == "python"


def test_search_text_query_with_filter(api: httpx.Client) -> None:
    """Combining text query with filters works correctly."""
    fixtures = _seed_search_fixtures(api)
    tag = fixtures["tag"]

    r = api.post(
        "/api/v1/search",
        json={
            "query": f"cardiac {tag}",
            "filters": [{"field": "resource_type", "op": "eq", "value": "model"}],
        },
    )
    assert r.status_code == 200
    payload = r.json()

    # Only the cardiac model should match (dataset is excluded by filter)
    ids = [item["id"] for item in payload["results"]]
    assert fixtures["model_id"] in ids
    assert fixtures["dataset_id"] not in ids


def test_search_aggregations(api: httpx.Client) -> None:
    """Aggregation buckets are returned with correct structure."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}],
            "aggs": ["resource_type", "execution_type", "format_tags"],
        },
    )
    assert r.status_code == 200
    payload = r.json()

    aggs = payload["aggs"]
    assert "resource_type" in aggs
    assert "execution_type" in aggs
    assert "format_tags" in aggs

    # Verify bucket structure
    for field_name, agg_result in aggs.items():
        assert "buckets" in agg_result
        for bucket in agg_result["buckets"]:
            assert "key" in bucket
            assert "count" in bucket
            assert isinstance(bucket["count"], int)
            assert bucket["count"] > 0


def test_search_aggregation_values(api: httpx.Client) -> None:
    """Aggregation bucket keys use clean enum values, not Python repr."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}],
            "aggs": ["resource_type", "format_tags"],
        },
    )
    assert r.status_code == 200
    aggs = r.json()["aggs"]

    # resource_type keys should be "model"/"dataset", not "ResourceType.MODEL"
    rt_keys = {b["key"] for b in aggs["resource_type"]["buckets"]}
    assert rt_keys <= {"model", "dataset", "tool"}
    assert "model" in rt_keys
    assert "dataset" in rt_keys

    # format_tags should be the actual tag strings
    ft_keys = {b["key"] for b in aggs["format_tags"]["buckets"]}
    assert "csv" in ft_keys
    assert "hdf5" in ft_keys


def test_search_aggregations_reflect_filters(api: httpx.Client) -> None:
    """Aggregation counts are computed on the filtered result set, not the full table."""
    fixtures = _seed_search_fixtures(api)

    # Agg scoped to one owner
    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["other_owner"]}],
            "aggs": ["resource_type"],
        },
    )
    assert r.status_code == 200
    buckets = r.json()["aggs"]["resource_type"]["buckets"]
    bucket_map = {b["key"]: b["count"] for b in buckets}

    # other_owner only has the nn_model (a model), no datasets
    assert "dataset" not in bucket_map
    assert bucket_map.get("model", 0) >= 1


def test_search_pagination(api: httpx.Client) -> None:
    """Pagination via limit/offset works at the DB level."""
    fixtures = _seed_search_fixtures(api)

    # Get page 1 (limit 1)
    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}],
            "limit": 1,
            "offset": 0,
        },
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["total"] == 2  # model + dataset
    assert len(payload["results"]) == 1

    first_id = payload["results"][0]["id"]

    # Get page 2
    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}],
            "limit": 1,
            "offset": 1,
        },
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["total"] == 2
    assert len(payload["results"]) == 1
    assert payload["results"][0]["id"] != first_id


def test_search_sort_by_name(api: httpx.Client) -> None:
    """Sorting by name works."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}],
            "sort": {"field": "name", "order": "asc"},
        },
    )
    assert r.status_code == 200
    names = [item["name"] for item in r.json()["results"]]
    assert names == sorted(names)


def test_search_no_text_query_has_null_scores(api: httpx.Client) -> None:
    """When no text query is provided, score should be null."""
    r = api.post("/api/v1/search", json={})
    assert r.status_code == 200
    for item in r.json()["results"]:
        assert item["score"] is None


def test_search_response_shape(api: httpx.Client) -> None:
    """Verify the full shape of a search result item."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={
            "filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}],
        },
    )
    assert r.status_code == 200
    item = r.json()["results"][0]

    expected_keys = {
        "id",
        "name",
        "resource_type",
        "location_uri",
        "description",
        "version",
        "status",
        "owner",
        "execution_type",
        "organisms",
        "domains",
        "modeling_scales",
        "format_tags",
        "created_at",
        "updated_at",
        "score",
    }
    assert set(item.keys()) == expected_keys


def test_search_invalid_filter_field_returns_400(api: httpx.Client) -> None:
    """Unknown filter field returns 400."""
    r = api.post(
        "/api/v1/search",
        json={"filters": [{"field": "nonexistent", "op": "eq", "value": "x"}]},
    )
    assert r.status_code == 400
    assert "nonexistent" in r.json()["error"]["detail"]


def test_search_invalid_filter_op_returns_400(api: httpx.Client) -> None:
    """Invalid operator for a field returns 400."""
    r = api.post(
        "/api/v1/search",
        json={"filters": [{"field": "resource_type", "op": "overlap", "value": "model"}]},
    )
    assert r.status_code == 400
    assert "overlap" in r.json()["error"]["detail"]


def test_search_invalid_agg_field_returns_400(api: httpx.Client) -> None:
    """Unknown aggregation field returns 400."""
    r = api.post(
        "/api/v1/search",
        json={"aggs": ["nonexistent_field"]},
    )
    assert r.status_code == 400
    assert "nonexistent_field" in r.json()["error"]["detail"]
