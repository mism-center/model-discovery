"""Parser check for metadata-package -> Resource mapping.

Runs against the bundled vivarium-chemotaxis example package checked in under
tests/unit/test-data/metadata-package/.
Requires the updated mism_registry schema (contacts, model_scales, io, ...).
"""

import dataclasses
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder

from mismapi.services.metadata_package import build_resource_from_package

_EXAMPLE_PKG = Path(__file__).resolve().parent / "test-data" / "metadata-package"


@pytest.mark.skipif(
    not (_EXAMPLE_PKG / "metadata.yaml").is_file(),
    reason=f"example metadata-package not found: {_EXAMPLE_PKG}",
)
def test_build_resource_from_example_package() -> None:
    r = build_resource_from_package(_EXAMPLE_PKG)

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
