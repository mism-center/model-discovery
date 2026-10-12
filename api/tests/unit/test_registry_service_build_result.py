"""Unit tests for RegistryService.apply_build_result / mark_build_started.

The execution API reports an envagent build back to discovery; a verified L3
build makes the model runnable with the built image, anything else marks the
build failed without touching the run recipe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from mism_registry.enums import (
    EnvBuildStatus,
    ExecutionType,
    ImageReviewStatus,
    ResourceRegistrationStatus,
    ResourceType,
    ResourceVersionStatus,
)
from mism_registry.in_memory import InMemoryRegistry
from mism_registry.resource import Resource
from mism_registry.types import EntryPoint, IODetail, Output

from mismapi.core.errors import APIError
from mismapi.schemas.registry import BuildResultCallback
from mismapi.services.authorization_service import AuthorizationService
from mismapi.services.registry_service import RegistryService

IMAGE = "docker.io/mismplatform/envbuild@sha256:8e05fd"


def _service(
    env_build_status: EnvBuildStatus = EnvBuildStatus.BUILDING,
    **resource_kwargs: Any,
) -> tuple[RegistryService, InMemoryRegistry]:
    """Service over an in-memory registry holding one approved model ``m-1``."""
    registry = InMemoryRegistry()
    registry.register_resource(
        Resource(
            id="m-1",
            name="Example Model",
            resource_type=ResourceType.MODEL,
            location_uri="irods:///m-1/0.1.0",
            execution_type=ExecutionType.PYTHON,
            version="0.1.0",
            version_status=ResourceVersionStatus.ACTIVE,
            owner="dana",
            registration_status=ResourceRegistrationStatus.APPROVED,
            env_build_status=env_build_status,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            **resource_kwargs,
        )
    )
    service = RegistryService(
        registry=registry, session=MagicMock(), authz=AuthorizationService(client=None)
    )
    return service, registry


def _result(**overrides: Any) -> BuildResultCallback:
    """A verified L3 result in the execution API's shape (extra keys ignored)."""
    body: dict[str, Any] = {
        "resource_id": "m-1",
        "run_id": "98d9da1c66",
        "job": {"name": "envbuild-98d9da1c66", "status": "succeeded", "exit_code": None},
        "outcome": "verified",
        "ladder_reached": "L3",
        "image": {"ref": IMAGE, "digest": "sha256:8e05fd"},
        "reason": "",
        "failure_class": None,
        "routes_to": "retry",
        "runtime": {
            "entrypoint": [],
            "install_mode": "mounted",
            "mount": {"code_path": "/model", "output_path": "/outputs"},
            "env_vars": {"MPLBACKEND": "Agg"},
        },
        "artifacts": {"annotation_patch": None},
        "attempts": [{"attempt": 1}],
        "verdict": {"entrypoint_used": "python run.py"},
    }
    body.update(overrides)
    return BuildResultCallback.model_validate(body)


def test_verified_l3_makes_model_runnable() -> None:
    service, _ = _service(
        entry_points=[EntryPoint(command="python other.py"), EntryPoint(command="python run.py")],
        io=IODetail(outputs=(Output(name="a"), Output(name="b", destination="/keep"))),
    )
    r = service.apply_build_result(_result())

    assert r.env_build_status == EnvBuildStatus.RUNNABLE
    assert r.containers[0].image_name == IMAGE
    assert r.containers[0].registry == "docker.io"
    assert r.image_review_status == ImageReviewStatus.IMAGE_APPROVED
    # Proven command moved to the front, the other one kept.
    assert [e.command for e in r.entry_points] == ["python run.py", "python other.py"]
    # Only empty destinations take the mount's output_path.
    assert r.io is not None
    assert [o.destination for o in r.io.outputs] == ["/outputs", "/keep"]


def test_unknown_command_is_prepended_and_output_added() -> None:
    service, _ = _service(entry_points=[EntryPoint(command="python other.py")])
    r = service.apply_build_result(
        _result(
            verdict={}, runtime={"entrypoint": ["python", "a b.py"], "mount": {"output_path": "/o"}}
        )
    )
    assert [e.command for e in r.entry_points] == ["python 'a b.py'", "python other.py"]
    assert r.io is not None
    assert [(o.name, o.destination) for o in r.io.outputs] == [("outputs", "/o")]


@pytest.mark.parametrize(
    "overrides",
    [
        {"ladder_reached": "L2"},
        {"outcome": "failed", "failure_class": "ABI_MISMATCH", "reason": "arrow"},
        {"image": None},
    ],
)
def test_non_verified_marks_build_failed_and_leaves_recipe(overrides: dict[str, Any]) -> None:
    service, _ = _service(entry_points=[EntryPoint(command="python other.py")])
    r = service.apply_build_result(_result(**overrides))

    assert r.env_build_status == EnvBuildStatus.BUILD_FAILED
    assert r.env_build_error
    assert r.containers == []
    assert [e.command for e in r.entry_points] == ["python other.py"]


def test_failure_error_text() -> None:
    service, _ = _service()
    r = service.apply_build_result(
        _result(outcome="failed", failure_class="ABI_MISMATCH", reason="arrow")
    )
    assert r.env_build_error == "ABI_MISMATCH: arrow"


def test_replay_of_applied_build_is_noop() -> None:
    service, _ = _service()
    first = service.apply_build_result(_result())
    again = service.apply_build_result(_result())
    assert again.env_build_status == EnvBuildStatus.RUNNABLE
    assert again.entry_points == first.entry_points


def test_ready_for_build_steps_through_building() -> None:
    service, _ = _service(env_build_status=EnvBuildStatus.READY_FOR_BUILD)
    assert service.apply_build_result(_result()).env_build_status == EnvBuildStatus.RUNNABLE


def test_not_ready_model_is_409() -> None:
    service, _ = _service(env_build_status=EnvBuildStatus.NOT_READY)
    with pytest.raises(APIError) as excinfo:
        service.apply_build_result(_result())
    assert excinfo.value.status_code == 409


def test_unknown_model_is_404() -> None:
    service, _ = _service()
    with pytest.raises(APIError) as excinfo:
        service.apply_build_result(_result(resource_id="nope"))
    assert excinfo.value.status_code == 404


def test_mark_build_started() -> None:
    service, _ = _service(env_build_status=EnvBuildStatus.READY_FOR_BUILD)
    assert service.mark_build_started("m-1").env_build_status == EnvBuildStatus.BUILDING
