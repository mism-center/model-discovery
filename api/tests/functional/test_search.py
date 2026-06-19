"""Live tests for POST /api/v1/search (full-text, filters, aggs)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from tests.functional.helpers import unique_name

pytestmark = pytest.mark.integration


def _seed_search_fixtures(api: httpx.Client) -> dict[str, str]:
    """Create a model and a dataset with unique names, return their ids and names."""
    tag = uuid.uuid4().hex[:8]

    r = api.post(
        "/api/v1/models",
        json={
            "name": f"Cardiac Simulator {tag}",
            "location_uri": "irods:///models/cardiac",
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
            "location_uri": "irods:///datasets/ecg",
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
            "location_uri": "irods:///models/nn",
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
    ids = [item["id"] for item in payload["results"]]
    assert fixtures["model_id"] in ids
    assert fixtures["dataset_id"] in ids

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

    model_score = next(
        (item["score"] for item in results if item["id"] == fixtures["model_id"]),
        None,
    )
    dataset_score = next(
        (item["score"] for item in results if item["id"] == fixtures["dataset_id"]),
        None,
    )
    assert model_score is not None and dataset_score is not None
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

    for _field_name, agg_result in aggs.items():
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

    rt_keys = {b["key"] for b in aggs["resource_type"]["buckets"]}
    assert rt_keys <= {"model", "dataset", "tool"}
    assert "model" in rt_keys
    assert "dataset" in rt_keys

    ft_keys = {b["key"] for b in aggs["format_tags"]["buckets"]}
    assert "csv" in ft_keys
    assert "hdf5" in ft_keys


def test_search_aggregations_reflect_filters(api: httpx.Client) -> None:
    """Aggregation counts are computed on the filtered result set, not the full table."""
    fixtures = _seed_search_fixtures(api)

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

    assert "dataset" not in bucket_map
    assert bucket_map.get("model", 0) >= 1


def test_search_pagination(api: httpx.Client) -> None:
    """Pagination via limit/offset works at the DB level."""
    fixtures = _seed_search_fixtures(api)

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
    assert payload["total"] == 2
    assert len(payload["results"]) == 1

    first_id = payload["results"][0]["id"]

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
        # Identity & description
        "id",
        "name",
        "resource_type",
        "location_uri",
        "description",
        "version",
        "status",
        # Authorship & attribution
        "owner",
        "authors",
        "organization",
        "contact_email",
        "publications",
        "funding",
        # Scientific context
        "organisms",
        "domains",
        "modeling_scales",
        "date_published",
        # Location & integrity
        "format_tags",
        "digest_sha256",
        "size_bytes",
        "external_ids",
        "license",
        # Execution
        "execution_type",
        "execution_ref",
        "io_spec",
        # System
        "metadata",
        "created_at",
        "updated_at",
        "score",
    }
    assert set(item.keys()) == expected_keys


def test_search_response_new_fields_default_values(api: httpx.Client) -> None:
    """New fields return correct defaults when not supplied at creation."""
    fixtures = _seed_search_fixtures(api)

    r = api.post(
        "/api/v1/search",
        json={"filters": [{"field": "owner", "op": "eq", "value": fixtures["owner"]}]},
    )
    assert r.status_code == 200
    item = r.json()["results"][0]

    assert item["authors"] == []
    assert item["publications"] == []
    assert item["funding"] == []
    assert item["organization"] == ""
    assert item["contact_email"] == ""
    assert item["organisms"] == []
    assert item["domains"] == []
    assert item["modeling_scales"] == []
    assert item["date_published"] is None
    assert item["digest_sha256"] == ""
    assert item["size_bytes"] is None
    assert item["external_ids"] == {}
    assert item["license"] == ""
    assert item["io_spec"] is None
    assert isinstance(item["metadata"], dict)


def test_create_model_with_full_fields_roundtrip(api: httpx.Client) -> None:
    """Create model with all new fields and verify they appear in the response."""
    name = unique_name("full-model")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "irods:///models/full",
            "execution_type": "docker",
            "description": "Full-field model",
            "authors": [
                {
                    "name": "Jane Doe",
                    "orcid": "0000-0001-2345-6789",
                    "affiliation": "RENCI",
                    "role": "developer",
                }
            ],
            "organization": "RENCI",
            "contact_email": "jane@renci.org",
            "publications": [
                {"title": "A paper", "doi": "10.1234/test", "url": "", "citation": ""}
            ],
            "funding": ["NIH R01", "NSF 2345"],
            "modeling_scales": ["cellular", "tissue"],
            "organisms": ["human", "mouse"],
            "domains": ["cardiology"],
            "date_published": "2024-03-15",
            "format_tags": ["onnx"],
            "digest_sha256": "abc123",
            "size_bytes": 4096,
            "external_ids": {"biomodels": "MODEL001"},
            "license": "MIT",
            "io_spec": {
                "inputs": [
                    {
                        "name": "voltage",
                        "tags": ["scalar"],
                        "required": True,
                        "description": "Membrane voltage",
                    }
                ],
                "outputs": [
                    {
                        "name": "current",
                        "tags": ["scalar"],
                        "required": True,
                        "description": "Ion current",
                    }
                ],
            },
        },
    )
    assert r.status_code == 201
    m = r.json()

    assert m["authors"] == [
        {
            "name": "Jane Doe",
            "orcid": "0000-0001-2345-6789",
            "affiliation": "RENCI",
            "role": "developer",
        }
    ]
    assert m["organization"] == "RENCI"
    assert m["contact_email"] == "jane@renci.org"
    assert m["publications"] == [
        {"title": "A paper", "doi": "10.1234/test", "url": "", "citation": ""}
    ]
    assert m["funding"] == ["NIH R01", "NSF 2345"]
    assert set(m["modeling_scales"]) == {"cellular", "tissue"}
    assert set(m["organisms"]) == {"human", "mouse"}
    assert m["domains"] == ["cardiology"]
    assert m["date_published"] == "2024-03-15"
    assert "onnx" in m["format_tags"]
    assert m["digest_sha256"] == "abc123"
    assert m["size_bytes"] == 4096
    assert m["external_ids"] == {"biomodels": "MODEL001"}
    assert m["license"] == "MIT"
    assert m["io_spec"]["inputs"][0]["name"] == "voltage"
    assert m["io_spec"]["outputs"][0]["name"] == "current"
    assert "updated_at" in m


def test_create_dataset_with_full_fields_roundtrip(api: httpx.Client) -> None:
    """Create dataset with all new fields and verify they appear in the response."""
    name = unique_name("full-dataset")
    r = api.post(
        "/api/v1/datasets",
        json={
            "name": name,
            "location_uri": "irods:///datasets/full",
            "description": "Full-field dataset",
            "authors": [
                {"name": "Bob Smith", "orcid": "", "affiliation": "UNC", "role": "curator"}
            ],
            "organization": "UNC",
            "contact_email": "bob@unc.edu",
            "publications": [
                {"title": "Dataset paper", "doi": "10.5678/data", "url": "", "citation": ""}
            ],
            "funding": ["NIH P41"],
            "modeling_scales": ["organ"],
            "organisms": ["rat"],
            "domains": ["neuroscience"],
            "date_published": "2023-11-01",
            "format_tags": ["csv", "hdf5"],
            "digest_sha256": "def456",
            "size_bytes": 1048576,
            "external_ids": {"zenodo": "123456"},
            "license": "CC-BY-4.0",
        },
    )
    assert r.status_code == 201
    d = r.json()

    assert d["authors"] == [
        {"name": "Bob Smith", "orcid": "", "affiliation": "UNC", "role": "curator"}
    ]
    assert d["organization"] == "UNC"
    assert d["contact_email"] == "bob@unc.edu"
    assert d["publications"] == [
        {"title": "Dataset paper", "doi": "10.5678/data", "url": "", "citation": ""}
    ]
    assert d["funding"] == ["NIH P41"]
    assert d["organisms"] == ["rat"]
    assert d["domains"] == ["neuroscience"]
    assert d["date_published"] == "2023-11-01"
    assert d["digest_sha256"] == "def456"
    assert d["size_bytes"] == 1048576
    assert d["external_ids"] == {"zenodo": "123456"}
    assert d["license"] == "CC-BY-4.0"
    assert "updated_at" in d


def test_update_model_new_fields(api: httpx.Client) -> None:
    """PUT /models/{id} updates new fields correctly."""
    name = unique_name("upd-model-new")
    r = api.post(
        "/api/v1/models",
        json={"name": name, "location_uri": "irods:///models/upd", "execution_type": "python"},
    )
    assert r.status_code == 201
    model_id = r.json()["id"]

    r = api.put(
        f"/api/v1/models/{model_id}",
        json={
            "organization": "Updated Org",
            "contact_email": "new@org.com",
            "organisms": ["zebrafish"],
            "license": "Apache-2.0",
            "digest_sha256": "newdigest",
        },
    )
    assert r.status_code == 200
    m = r.json()
    assert m["organization"] == "Updated Org"
    assert m["contact_email"] == "new@org.com"
    assert m["organisms"] == ["zebrafish"]
    assert m["license"] == "Apache-2.0"
    assert m["digest_sha256"] == "newdigest"


def test_update_dataset_new_fields(api: httpx.Client) -> None:
    """PUT /datasets/{id} updates new fields correctly."""
    name = unique_name("upd-dataset-new")
    r = api.post(
        "/api/v1/datasets",
        json={"name": name, "location_uri": "irods:///datasets/upd"},
    )
    assert r.status_code == 201
    dataset_id = r.json()["id"]

    r = api.put(
        f"/api/v1/datasets/{dataset_id}",
        json={
            "authors": [{"name": "Alice", "orcid": "", "affiliation": "MIT", "role": "author"}],
            "funding": ["DOE"],
            "modeling_scales": ["population"],
            "size_bytes": 512,
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["authors"] == [{"name": "Alice", "orcid": "", "affiliation": "MIT", "role": "author"}]
    assert d["funding"] == ["DOE"]
    assert d["modeling_scales"] == ["population"]
    assert d["size_bytes"] == 512


def test_list_models_response_includes_new_fields(api: httpx.Client) -> None:
    """GET /models results include all new Resource fields."""
    name = unique_name("list-model-new")
    r = api.post(
        "/api/v1/models",
        json={
            "name": name,
            "location_uri": "irods:///models/list-new",
            "execution_type": "docker",
            "organization": "TestOrg",
            "organisms": ["human"],
        },
    )
    assert r.status_code == 201

    r = api.get("/api/v1/models", params={"name": name})
    assert r.status_code == 200
    item = r.json()["results"][0]
    assert item["organization"] == "TestOrg"
    assert item["organisms"] == ["human"]
    assert "authors" in item
    assert "updated_at" in item
    assert "io_spec" in item


def test_list_datasets_response_includes_new_fields(api: httpx.Client) -> None:
    """GET /datasets results include all new Resource fields."""
    name = unique_name("list-dataset-new")
    r = api.post(
        "/api/v1/datasets",
        json={
            "name": name,
            "location_uri": "irods:///datasets/list-new",
            "license": "MIT",
            "size_bytes": 100,
        },
    )
    assert r.status_code == 201

    r = api.get("/api/v1/datasets", params={"name": name})
    assert r.status_code == 200
    item = r.json()["results"][0]
    assert item["license"] == "MIT"
    assert item["size_bytes"] == 100
    assert "authors" in item
    assert "updated_at" in item


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
