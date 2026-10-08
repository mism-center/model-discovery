"""Parser check for metadata-package -> Resource mapping.

Runs against the bundled vivarium-chemotaxis example package checked in under
tests/unit/test-data/metadata-package/.
Requires the updated mism_registry schema (contacts, model_scales, io, ...).
"""

import dataclasses
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder

from mismapi.services.metadata_package import _build_compute, _build_io, build_resource_from_package

_EXAMPLE_PKG = Path(__file__).resolve().parent / "test-data" / "metadata-package"


@pytest.mark.skipif(
    not (_EXAMPLE_PKG / "metadata.yaml").is_file(),
    reason=f"example metadata-package not found: {_EXAMPLE_PKG}",
)
def test_build_resource_from_example_package() -> None:
    r, warnings = build_resource_from_package(_EXAMPLE_PKG)

    # Section A: identity + biology unwrapped to plain values.
    assert r.name == "Vivarium-chemotaxis"
    assert r.version == "0.0.2"
    assert r.license == "MIT"
    assert r.multiscale is True
    assert r.model_scales == ["molecular", "cellular", "population"]
    assert r.organisms == ["Escherichia coli"]
    assert [a.name for a in r.authors] == ["Eran Agmon", "Ryan Spangler"]

    # Section B: execution mapped, environment_kind -> ExecutionType.
    # Counts are left as non-empty checks — the example package is regenerated
    # by the annotator, so exact dependency/entry-point counts drift.
    assert r.execution_type is not None and r.execution_type.value == "pip"
    assert len(r.dependencies) > 0
    assert len(r.entry_points) > 0

    # Container recipe parsed (denormalized onto a run at prepare_run time).
    # This example has no container recipe, so nothing to assert on unless
    # a future regeneration of the fixture adds one.
    if len(r.containers) > 0:
        assert r.containers[0].kind == "docker"

    # New Argument fields (enums / data_type / position) must survive parsing —
    # they drive run-argument validation and to_cli rendering. The paper
    # experiments entry point has a constrained positional argument.
    positional = [
        a
        for ep in r.entry_points
        for a in ep.arguments
        if a.position is not None and a.position > 0
    ]
    assert positional, "expected at least one positional argument in the example"
    experiment = next(a for a in positional if a.name == "experiment_id")
    assert experiment.position == 1
    assert experiment.data_type == "str"
    assert experiment.enums is not None and "7b" in experiment.enums

    # Section C: rich I/O present.
    assert r.io is not None
    assert len(r.io.parameters) > 0
    assert len(r.io.outputs) > 0

    # The endpoint returns asdict(...) through FastAPI's encoder — must serialize.
    jsonable_encoder(dataclasses.asdict(r))

    # Fixture's experiment_protocol.timestep/duration are deliberately prose
    # strings (not single numbers) — confirm they're coerced to None with a
    # localized warning, not silently stored or left to crash the API layer's
    # ComputeDTO/ExperimentProtocolDTO later (see Docs/rangefix/Range-Value-Fix-Plan.md).
    assert r.io.experiment_protocol is not None
    assert r.io.experiment_protocol.timestep is None
    assert r.io.experiment_protocol.duration is None
    assert any("io.experiment_protocol.timestep" in w for w in warnings)
    assert any("io.experiment_protocol.duration" in w for w in warnings)


@pytest.mark.parametrize("field", ["cpu_cores", "memory_gb", "typical_runtime"])
def test_build_compute_rejects_non_numeric_value(field: str) -> None:
    warnings: list[str] = []
    compute = _build_compute(
        {field: {"value": "~30 minutes for the larger efficacy simulation"}}, warnings
    )
    assert getattr(compute, field) is None
    assert any(f"execution.compute.{field}" in w for w in warnings)


def test_build_compute_accepts_numeric_ish_string_for_cpu_cores() -> None:
    warnings: list[str] = []
    compute = _build_compute({"cpu_cores": {"value": "4.0"}}, warnings)
    assert compute is not None
    assert compute.cpu_cores == 4
    assert warnings == []


def test_build_compute_passes_through_none_and_clean_numbers() -> None:
    warnings: list[str] = []
    compute = _build_compute({"cpu_cores": {"value": None}, "memory_gb": {"value": 8}}, warnings)
    assert compute is not None
    assert compute.cpu_cores is None
    assert compute.memory_gb == 8.0
    assert warnings == []


@pytest.mark.parametrize("field", ["timestep", "duration"])
def test_build_io_experiment_protocol_rejects_range_string(field: str) -> None:
    warnings: list[str] = []
    io = _build_io({"experiment_protocol": {field: {"value": "10-20"}}}, warnings)
    assert io is not None
    assert getattr(io.experiment_protocol, field) is None
    assert any(f"io.experiment_protocol.{field}" in w for w in warnings)
