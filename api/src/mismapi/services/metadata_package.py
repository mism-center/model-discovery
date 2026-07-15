"""Parse a biomodel-annotator ``metadata-package`` into a ``Resource``.

A metadata-package directory holds two YAML files (see metadata-schema
``schema.md`` and ``scripts/align_annotation.py``):

  * ``metadata.yaml``  — Section A: model identity, biology, attribution.
  * ``execution.yaml`` — Section B/C: how to run it + rich I/O detail.

Both wrap leaf values in ``{value, source, confidence}`` / ontology sub-blocks;
this module unwraps those down to the plain value strings that ``Resource``
stores (it keeps values only — IRIs/source/confidence are dropped, per the
library contract). This is the "real ingestion" the library docs defer to the
discovery API. Ported from the non-packaged ``align_annotation.py`` probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from mism_registry.enums import ExecutionType, ResourceType
from mism_registry.resource import Resource
from mism_registry.types import (
    Argument,
    Author,
    Compute,
    Contact,
    Container,
    DataInput,
    Dependency,
    EntryPoint,
    ExperimentProtocol,
    InitialCondition,
    IODetail,
    Output,
    Parameter,
    Publication,
    RelatedResource,
    TestSpec,
)

# The two files that make up a metadata-package.
METADATA_FILE = "metadata.yaml"
EXECUTION_FILE = "execution.yaml"


def _val(x: Any) -> Any:
    """Unwrap a ``{value, ...}`` leaf to its value; pass scalars through."""
    if isinstance(x, dict) and "value" in x:
        return x["value"]
    return x


def _s(x: Any) -> str:
    """Coerce None/missing to empty string."""
    return "" if x is None else str(x)


def _terms(items: Any) -> list[str]:
    """Ontology-mapped list ``[{value, iri, ...}]`` -> ``[value]`` (IRIs dropped)."""
    return [it["value"] for it in items or []]


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def build_resource_from_package(pkg_dir: Path) -> Resource:
    """Map a metadata-package directory onto a ``Resource``.

    Reads ``metadata.yaml`` + ``execution.yaml`` from ``pkg_dir``. Raises
    ``FileNotFoundError`` if either file is missing, ``yaml.YAMLError`` on
    malformed YAML, and ``KeyError`` if a required key (e.g. ``model.name``) is
    absent — callers translate these into HTTP errors.
    """
    meta = _load(pkg_dir / METADATA_FILE)
    execu = _load(pkg_dir / EXECUTION_FILE)
    m = meta["model"]
    ext = m.get("external_identifier", {}) or {}

    # -- Section A: model -------------------------------------------------
    bio = m.get("biology", {}) or {}
    authors = [
        Author(
            name=a["name"],
            affiliation=_s(a.get("affiliation")),
            orcid=_s(a.get("orcid")),
            role=_s(a.get("role")),
        )
        for a in m.get("authors", []) or []
    ]
    contacts = [
        Contact(
            name=c["name"],
            role=_s(c.get("role")),
            email=_s(c.get("email")),
            affiliation=_s(c.get("affiliation")),
        )
        for c in m.get("contacts", []) or []
    ]
    publications = [
        Publication(
            title=p["title"],
            doi=_s(p.get("doi")),
            pmid=_s(p.get("pmid")),
            url=_s(p.get("url")),
        )
        for p in m.get("publications", []) or []
    ]
    related = [
        RelatedResource(
            qualifier=r["qualifier"],
            scheme=_s((r.get("identifier") or {}).get("scheme")),
            value=_s((r.get("identifier") or {}).get("value")),
        )
        for r in m.get("related_resources", []) or []
    ]

    # -- Section B: execution ---------------------------------------------
    lang = execu["execution"].get("language", {}) or {}
    exec_type = _to_execution_type(_val(execu["execution"].get("environment_kind")))

    deps: list[Dependency] = []
    for kind, lst in (execu["execution"].get("dependencies", {}) or {}).items():
        for d in lst or []:
            deps.append(
                Dependency(
                    name=d["name"],
                    version_constraint=_s(d.get("version_constraint")),
                    kind=kind,
                    group=_s(d.get("group")),
                )
            )
    containers = [
        Container(kind=c["kind"], file=_s(c.get("file")), image_name=_s(c.get("image_name")))
        for c in execu["execution"].get("containers", []) or []
    ]
    compute = _build_compute(execu["execution"].get("compute"))
    entry_points = [
        EntryPoint(
            command=e["command"],
            purpose=_s(e.get("purpose")),
            arguments=tuple(
                Argument(
                    name=a["name"],
                    description=_s(a.get("description")),
                    default=a.get("default"),
                )
                for a in e.get("arguments", []) or []
            ),
        )
        for e in execu["execution"].get("entry_points", []) or []
    ]
    tests_d = execu["execution"].get("tests")
    tests = (
        TestSpec(framework=_s(tests_d.get("framework")), invocation=_s(tests_d.get("invocation")))
        if tests_d
        else None
    )

    # -- Section C: io ----------------------------------------------------
    io = _build_io(execu.get("io"))

    return Resource(
        name=m["name"]["value"],
        resource_type=ResourceType.MODEL,
        location_uri=ext.get("value", ""),
        short_description=_s(_val(m.get("short_description"))),
        description=_s(_val(m.get("long_description"))),
        version=_s(_val(m.get("version"))),
        external_ids={ext["scheme"]: ext["value"]} if ext.get("scheme") else {},
        license=(m.get("license", {}) or {}).get("spdx_id", ""),
        authors=authors,
        contacts=contacts,
        publications=publications,
        related_resources=related,
        funding=[str(x) for x in m.get("funding", []) or []],
        model_scales=[_val(s) for s in m.get("model_scales", []) or []],
        organisms=_terms(bio.get("species")),
        domains=_terms(bio.get("topic_category")),
        infectious_agents=_terms(bio.get("infectious_agent")),
        health_conditions=_terms(bio.get("health_condition")),
        biological_processes=_terms(bio.get("biological_processes")),
        molecular_entities=_terms(bio.get("molecular_entities")),
        proteins_genes=[p["value"] for p in bio.get("proteins_genes", []) or []],
        model_class=_terms(m.get("model_class")),
        formalism=_terms(m.get("formalism")),
        determinism=_s(m.get("determinism")) or "unknown",
        time_dynamics=_s(m.get("time_dynamics")) or "unknown",
        spatial=_s(m.get("spatial")) or "unknown",
        multiscale=m.get("multiscale"),
        execution_type=exec_type,
        execution_status=_s(execu["execution"].get("status")),
        language_name=_s(lang.get("name")),
        language_version=_s(lang.get("version_constraint")),
        execution_notes=_s(execu["execution"].get("notes")),
        dependencies=deps,
        containers=containers,
        compute=compute,
        entry_points=entry_points,
        tests=tests,
        io=io,
    )


def _to_execution_type(kind: Any) -> ExecutionType | None:
    """Map ``environment_kind`` onto the ExecutionType enum, else OTHER/None."""
    if not kind:
        return None
    try:
        return ExecutionType(kind)
    except ValueError:
        return ExecutionType.OTHER


def _build_compute(c: Any) -> Compute | None:
    if not c:
        return None
    tr = c.get("typical_runtime", {}) or {}
    return Compute(
        cpu_cores=_val(c.get("cpu_cores")),
        memory_gb=_val(c.get("memory_gb")),
        gpu_required=_val(c.get("gpu_required")),
        parallelism=_s(c.get("parallelism")),
        typical_runtime=_val(tr),
        typical_runtime_unit=_s(tr.get("unit") if isinstance(tr, dict) else None),
    )


def _build_io(io: Any) -> IODetail | None:
    if not io:
        return None
    inp = io.get("inputs", {}) or {}
    ep = io.get("experiment_protocol")
    protocol = None
    if ep:
        ts, du = ep.get("timestep", {}) or {}, ep.get("duration", {}) or {}
        protocol = ExperimentProtocol(
            description=_s(ep.get("description")),
            timestep=_val(ts),
            timestep_unit=_s(ts.get("unit") if isinstance(ts, dict) else None),
            duration=_val(du),
            duration_unit=_s(du.get("unit") if isinstance(du, dict) else None),
            observables=tuple(ep.get("observables", []) or []),
        )
    return IODetail(
        parameters=tuple(
            Parameter(
                name=p["name"],
                description=_s(p.get("description")),
                default_value=p.get("default_value"),
                unit=_s(_val(p.get("unit"))),
                biological_meaning=_s(_val(p.get("biological_meaning"))),
            )
            for p in inp.get("parameters", []) or []
        ),
        initial_conditions=tuple(
            InitialCondition(name=i["name"], value=i.get("value"), unit=_s(_val(i.get("unit"))))
            for i in inp.get("initial_conditions", []) or []
        ),
        data_inputs=tuple(
            DataInput(
                name=d["name"],
                purpose=_s(d.get("purpose")),
                format=_s(_val(d.get("format"))),
                required=bool(d.get("required", True)),
            )
            for d in inp.get("data_inputs", []) or []
        ),
        outputs=tuple(
            Output(
                name=o["name"],
                description=_s(o.get("description")),
                quantity_kind=_s(_val(o.get("quantity_kind"))),
                unit=_s(_val(o.get("unit"))),
                format=_s(_val(o.get("format"))),
                destination=_s(o.get("destination")),
            )
            for o in io.get("outputs", []) or []
        ),
        experiment_protocol=protocol,
    )
