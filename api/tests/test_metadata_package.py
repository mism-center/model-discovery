"""Parser check for metadata-package -> Resource mapping.

Runs against the real vivarium-chemotaxis example package if it's checked out
next to this repo; skips otherwise (external repo, not always present in CI).
Requires the updated mism_registry schema (contacts, model_scales, io, ...).
"""

import dataclasses
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder

from mismapi.services.metadata_package import build_resource_from_package

# api/tests -> api -> model-discovery -> mism-center
_EXAMPLE_PKG = Path(__file__).resolve().parents[3] / "vivarium-chemotaxis" / "metadata-package"


@pytest.mark.skipif(
    not (_EXAMPLE_PKG / "metadata.yaml").is_file(),
    reason="example metadata-package not checked out",
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
    assert r.execution_type is not None and r.execution_type.value == "pip"
    assert len(r.dependencies) == 6
    assert len(r.entry_points) == 3

    # Section C: rich I/O present.
    assert r.io is not None
    assert len(r.io.parameters) == 13
    assert len(r.io.outputs) == 4

    # The endpoint returns asdict(...) through FastAPI's encoder — must serialize.
    jsonable_encoder(dataclasses.asdict(r))
