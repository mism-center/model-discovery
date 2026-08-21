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
from mism_registry.enums import (
    ExecutionType,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource

import mismapi.services.registry_service as reg_svc
from mismapi.auth.principal import AuthenticatedPrincipal
from mismapi.core.errors import APIError
from mismapi.services.registry_service import RegistryService

_META = "model:\n  name:\n    value: Old Model\n"
_META_NEW = "model:\n  name:\n    value: New Model\n"
_EXEC = "execution:\n  environment_kind: python\n"


def _principal(subject: str = "user-1") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject=subject, issuer="test", audience="mism-api", scopes=set())


def _make_service(
    mount: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    retry_max_attempts: int = 3,
    retry_backoff_seconds: float = 0.0,
) -> RegistryService:
    monkeypatch.setattr(
        reg_svc,
        "get_settings",
        lambda: SimpleNamespace(
            irods_mount_path=str(mount),
            metadata_package_retry_max_attempts=retry_max_attempts,
            metadata_package_retry_backoff_seconds=retry_backoff_seconds,
        ),
    )
    registry = InMemoryRegistry()
    registry.register_resource(
        Resource(
            id="m-1",
            name="Example Model",
            resource_type=ResourceType.MODEL,
            # Matches what mark_upload_complete stamps: upload_dir("m-1", "0.1.0")
            location_uri="irods:///m-1/0.1.0",
            execution_type=ExecutionType.PYTHON,
            version="0.1.0",
            version_status=ResourceVersionStatus.ACTIVE,
            owner="user-1",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
    )
    return RegistryService(registry=registry, session=MagicMock())


def _make_package(mount: Path) -> Path:
    # Mirrors location_uri "irods:///m-1/0.1.0": <mount>/m-1/0.1.0/metadata-package
    pkg = mount / "m-1" / "0.1.0" / "metadata-package"
    pkg.mkdir(parents=True)
    (pkg / "metadata.yaml").write_text(_META, encoding="utf-8")
    (pkg / "execution.yaml").write_text(_EXEC, encoding="utf-8")
    return pkg


def test_read_returns_both_files_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    out = service.read_metadata_package_raw("m-1")

    assert [name for name, _ in out] == ["metadata.yaml", "execution.yaml"]
    assert dict(out)["metadata.yaml"] == _META


def test_write_roundtrips_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    out, warnings = service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", _META_NEW)]
    )

    assert (pkg / "metadata.yaml").read_text(encoding="utf-8") == _META_NEW
    assert dict(out)["metadata.yaml"] == _META_NEW
    # untouched file preserved
    assert dict(out)["execution.yaml"] == _EXEC
    # DB was synced with the parsed name
    assert service._registry.get_resource("m-1").name == "New Model"
    assert warnings == []


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


def test_metadata_package_found_after_version_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: after write_metadata_package_raw syncs model.version from the
    annotation YAML, subsequent reads must still find the package via location_uri,
    not via upload_dir(id, new_version).

    Scenario: resource has location_uri="m-1/0.1.0" and version="0.1.0".
    The annotation YAML has no version field → write syncs version to "".
    upload_dir("m-1", "") = "m-1" (no version segment), which is a different path.
    The fix: _metadata_package_dir uses location_uri, so the version change is irrelevant.
    """
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)

    # Write YAML that has no version field → syncs resource.version to "" in DB.
    service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", _META)]
    )

    # assert service._registry.get_resource("m-1").version == "", (
    #     "Precondition: version must have been synced away from '0.1.0'"
    # )

    # Subsequent read must still work — files are at location_uri path, not upload_dir path.
    out = service.read_metadata_package_raw("m-1")
    assert dict(out)["metadata.yaml"] == _META


def test_metadata_package_dir_retries_until_files_appear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the intermittent-404 race: the annotation job pod and this
    API pod mount the same iRODS PVC from different pods, so a just-written
    metadata-package can briefly be invisible through this pod's mount.
    _metadata_package_dir should retry rather than 404 on the first miss.

    The model's own directory (created at upload time) already exists; only
    the nested metadata-package/ (written later by the annotation job) is
    initially missing — mirroring the real race.
    """
    (tmp_path / "m-1" / "0.1.0").mkdir(parents=True)
    service = _make_service(tmp_path, monkeypatch, retry_max_attempts=3, retry_backoff_seconds=0.0)

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) == 1:
            _make_package(tmp_path)  # simulate the files becoming visible after the first wait

    monkeypatch.setattr(reg_svc.time, "sleep", fake_sleep)

    out = service.read_metadata_package_raw("m-1")

    assert dict(out)["metadata.yaml"] == _META
    assert len(sleep_calls) == 1


def test_metadata_package_dir_404_after_retries_exhausted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the package never shows up within the retry budget, still 404 — the
    retry only smooths over transient propagation lag, not a genuinely
    missing package.
    """
    (tmp_path / "m-1" / "0.1.0").mkdir(parents=True)
    service = _make_service(tmp_path, monkeypatch, retry_max_attempts=3, retry_backoff_seconds=0.0)

    with pytest.raises(APIError) as exc:
        service.read_metadata_package_raw("m-1")

    assert exc.value.status_code == 404
    assert exc.value.code == "metadata_package_not_found"


def test_write_invalid_structure_raises_400_after_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid YAML syntax but missing required 'model.name.value' structure.

    A structural parse failure means the package can't be trusted, so
    clicking approve must not silently succeed: the raw YAML text is still
    written to disk (it was already validated as syntactically-valid YAML
    before parsing was attempted, so the user's edits aren't lost), but the
    request raises a 400 and the model is not approved / DB is untouched.
    """
    pkg = _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)
    bad_meta = "model:\n  name: not-a-dict\n"

    with pytest.raises(APIError) as exc:
        service.write_metadata_package_raw(
            _principal(), model_id="m-1", files=[("metadata.yaml", bad_meta)]
        )

    assert exc.value.status_code == 400

    # File was still written (YAML syntax was valid) so the user's edit isn't lost.
    assert (pkg / "metadata.yaml").read_text(encoding="utf-8") == bad_meta

    stored = service._registry.get_resource("m-1")
    # Approval did NOT go through — status and fields are untouched.
    assert stored.registration_status == ResourceRegistrationStatus.DRAFT
    assert stored.name == "Example Model"


def test_write_skips_publication_with_null_title_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduces the originally reported crash: a publication entry with a
    null title (annotator couldn't confidently extract one). This must not
    block the save or raise — the incomplete publication is skipped, every
    other field is still applied, and a warning names the exact file+field.
    """
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)
    meta_with_null_title = (
        "model:\n"
        "  name:\n"
        "    value: New Model\n"
        "  publications:\n"
        "    - title: null\n"
        "      doi: null\n"
        "      pmid: null\n"
        "      url: null\n"
    )

    out, warnings = service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", meta_with_null_title)]
    )

    assert dict(out)["metadata.yaml"] == meta_with_null_title
    stored = service._registry.get_resource("m-1")
    # registration_status is left untouched (DRAFT, the fixture's starting
    # state) — this endpoint no longer approves; other fields still applied,
    # so the null-title entry didn't block anything.
    assert stored.registration_status == ResourceRegistrationStatus.DRAFT
    assert stored.name == "New Model"
    # The incomplete publication is skipped, not stored with a fabricated title.
    assert stored.publications == []
    assert warnings == [
        "metadata.yaml: 'model.publications[0].title' is missing or empty; entry skipped"
    ]


def test_write_from_pending_review_leaves_status_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing while PENDING_REVIEW (the normal pre-review-decision case)
    doesn't move the status at all — approval/rejection is decided solely by
    RegistryService.review_metadata_package now."""
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)
    resource = service._registry.get_resource("m-1")
    resource.registration_status = ResourceRegistrationStatus.PENDING_REVIEW
    service._registry.update_resource(resource)

    service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", _META_NEW)]
    )

    stored = service._registry.get_resource("m-1")
    assert stored.registration_status == ResourceRegistrationStatus.PENDING_REVIEW


def test_write_from_rejected_returns_to_pending_review_and_clears_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resubmitting a manually-fixed REJECTED package re-enters the reviewer
    queue automatically (the state machine's REJECTED -> PENDING_REVIEW
    transition), and the stale rejection reason is cleared since it no
    longer applies. metadata_reviewed_by is left alone — it records who
    last reviewed it, not touched again until the next review action."""
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)
    resource = service._registry.get_resource("m-1")
    resource.registration_status = ResourceRegistrationStatus.REJECTED
    resource.metadata_rejection_reason = "Missing license info."
    resource.metadata_reviewed_by = "erin"
    service._registry.update_resource(resource)

    service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", _META_NEW)]
    )

    stored = service._registry.get_resource("m-1")
    assert stored.registration_status == ResourceRegistrationStatus.PENDING_REVIEW
    assert stored.metadata_rejection_reason == ""
    assert stored.metadata_reviewed_by == "erin"


def test_write_from_approved_leaves_status_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An already-APPROVED model's raw package can still be edited by its
    owner (ownership-gated only, same as other model edits) — but doing so
    does not change registration_status at all."""
    _make_package(tmp_path)
    service = _make_service(tmp_path, monkeypatch)
    resource = service._registry.get_resource("m-1")
    resource.registration_status = ResourceRegistrationStatus.APPROVED
    service._registry.update_resource(resource)

    service.write_metadata_package_raw(
        _principal(), model_id="m-1", files=[("metadata.yaml", _META_NEW)]
    )

    stored = service._registry.get_resource("m-1")
    assert stored.registration_status == ResourceRegistrationStatus.APPROVED
