"""Unit tests for reading/writing raw metadata-package YAML.

Exercises the real filesystem path (not the mocked-service endpoint tests):
the package dir is resolved under a temp iRODS mount, and writes must be
validated (known filename + parseable YAML) before anything is overwritten.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from mism_registry.enums import ExecutionType, ResourceType, ResourceVersionStatus
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

import mismapi.services.registry_service as reg_svc
from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService

_META = "model:\n  name: old\n"
_EXEC = "execution:\n  status: ok\n"


def _principal(subject: str = "user-1") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _make_service(mount: Path, monkeypatch: pytest.MonkeyPatch) -> RegistryService:
    monkeypatch.setattr(
        reg_svc, "get_settings", lambda: SimpleNamespace(irods_mount_path=str(mount))
    )
    registry = InMemoryRegistry()
    registry.register_resource(
        Resource(
            id="m-1",
            name="Example Model",
            resource_type=ResourceType.MODEL,
            location_uri="irods:///models/m-1",
            execution_type=ExecutionType.PYTHON,
            version="0.1.0",
            version_status=ResourceVersionStatus.ACTIVE,
            owner="user-1",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    return RegistryService(registry=registry, session=MagicMock())


def _make_package(mount: Path) -> Path:
    # Mirrors upload_dir(<id>, <version>): <mount>/m-1/0.1.0/metadata-package
    pkg = mount / "m-1" / "0.1.0" / "metadata-package"
    pkg.mkdir(parents=True)
    (pkg / "metadata.yaml").write_text(_META, encoding="utf-8")
    (pkg / "execution.yaml").write_text(_EXEC, encoding="utf-8")
    return pkg


def test_read_returns_both_files_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    out = service.read_metadata_package_raw("m-1")

    assert [name for name, _ in out] == ["metadata.yaml", "execution.yaml"]
    assert dict(out)["metadata.yaml"] == _META


def test_write_roundtrips_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    out = service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", "model:\n  name: new\n")]
    )

    assert (pkg / "metadata.yaml").read_text(encoding="utf-8") == "model:\n  name: new\n"
    assert dict(out)["metadata.yaml"] == "model:\n  name: new\n"
    # untouched file preserved
    assert dict(out)["execution.yaml"] == _EXEC


def test_write_rejects_unknown_filename_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    with pytest.raises(APIError) as exc:
        service.write_metadata_package_raw(
            _principal(), model_id="m-1", files=[("../escape.yaml", "x: 1\n")]
        )

    assert exc.value.status_code == 400
    assert (pkg / "metadata.yaml").read_text(encoding="utf-8") == _META  # nothing written


def test_write_is_all_or_nothing_on_bad_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    with pytest.raises(APIError) as exc:
        service.write_metadata_package_raw(
            _principal(),
            model_id="m-1",
            files=[
                ("metadata.yaml", "model:\n  name: new\n"),  # valid
                ("execution.yaml", "key: [unclosed\n"),  # malformed
            ],
        )

    assert exc.value.status_code == 400
    # valid file must NOT have been written because a later one failed validation
    assert (pkg / "metadata.yaml").read_text(encoding="utf-8") == _META


def test_write_rejects_other_owners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    with pytest.raises(APIError) as exc:
        service.write_metadata_package_raw(
            _principal("user-2"), model_id="m-1", files=[("metadata.yaml", _META)]
        )

    assert exc.value.status_code == 403
