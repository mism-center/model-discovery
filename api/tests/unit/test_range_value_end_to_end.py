"""End-to-end check that a metadata-package with range/prose values in the
five numeric-scoped fields no longer crashes GET /models/{id} (MISM-308).

Exercises the real chain: build_resource_from_package -> RegistryService ->
the actual FastAPI route -> ComputeDTO/ExperimentProtocolDTO construction.
Phase 1's unit tests (test_metadata_package.py) already prove the ingest
layer nulls these fields; this proves the full HTTP response doesn't 500
once it does -- the same chain that 500'd for real on mism-dev.renci.org
for models d1cd5d1a-... and 42e1c7ea-... (see Docs/rangefix/Range-Value-Fix-Plan.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

import mismapi.services.registry_service as reg_svc
from mismapi.core.deps import _get_registry_service
from mismapi.main import create_app
from mismapi.services.registry_service import RegistryService

from ..conftest import make_settings

_METADATA = """
schema_version: "0.1"
model:
  name: { value: "smoke-test", source: "test", confidence: high }
  short_description: { value: "test", source: "test", confidence: high }
  long_description: { value: "test", source: "test", confidence: high }
  version: { value: "0.1", source: "test", confidence: high }
  external_identifier: { scheme: "url", value: "https://example.com", source: "test" }
  multiscale: false
  model_scales: [{ value: "cellular", source: "test", confidence: high }]
  authors: [{ name: "Test Author", affiliation: "Test", source: "test" }]
  contacts:
    - name: "Test Contact"
      role: "maintainer"
      email: "a@b.com"
      affiliation: "Test"
      source: "test"
  license: { spdx_id: "MIT", source: "test", confidence: high }
  publications: [{ title: "Test Pub", url: "https://example.com", source: "test" }]
provenance: {}
"""
_EXECUTION = """
schema_version: "0.1"
execution:
  status: characterized
  language: { name: "Python", source: "test" }
  environment_kind: { value: "pip", source: "test" }
  entry_points:
    - { command: "python run.py", purpose: "run", source: "run.py", confidence: high }
  compute:
    typical_runtime:
      value: "~30 minutes for the larger efficacy simulation"
      unit: minutes
      source: test
      confidence: high
io:
  experiment_protocol:
    duration:
      value: "300-700 ticks in canonical studies; 1500 ticks at scale"
      unit: hour
      source: test
      confidence: high
provenance: {}
"""


def test_get_model_survives_range_values_in_numeric_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "m-range" / "0.1.0" / "metadata-package"
    pkg.mkdir(parents=True)
    (pkg / "metadata.yaml").write_text(_METADATA, encoding="utf-8")
    (pkg / "execution.yaml").write_text(_EXECUTION, encoding="utf-8")

    monkeypatch.setattr(
        reg_svc,
        "get_settings",
        lambda: SimpleNamespace(
            irods_mount_path=str(tmp_path),
            metadata_package_retry_max_attempts=3,
            metadata_package_retry_backoff_seconds=0.0,
        ),
    )
    registry = InMemoryRegistry()
    registry.register_resource(
        Resource(
            id="m-range",
            name="smoke-test",
            resource_type=ResourceType.MODEL,
            location_uri="irods:///m-range/0.1.0",
            execution_type=ExecutionType.PYTHON,
            version="0.1.0",
            version_status=ResourceVersionStatus.ACTIVE,
            registration_status=ResourceRegistrationStatus.APPROVED,
            owner="user-1",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    service = RegistryService(registry=registry, session=MagicMock())

    # Real ingest path -- same one Phase 1 fixed.
    resource, warnings = service.parse_metadata_package("m-range")
    assert any("execution.compute.typical_runtime" in w for w in warnings)
    assert any("io.experiment_protocol.duration" in w for w in warnings)

    stored = registry.get_resource("m-range")
    stored.compute = resource.compute
    stored.io = resource.io
    registry.update_resource(stored)

    app = create_app(settings=make_settings())
    app.dependency_overrides[_get_registry_service] = lambda: service
    with TestClient(app) as client:
        resp = client.get("/api/v1/models/m-range")

    assert resp.status_code == 200
    body = resp.json()
    assert body["compute"]["typical_runtime"] is None
    assert body["io"]["experiment_protocol"]["duration"] is None
