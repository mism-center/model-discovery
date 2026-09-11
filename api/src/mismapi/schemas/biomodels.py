"""The BioModels model-id format, and DTOs for the subset of a record the
gateway re-publishes.

Note that `accession` on the DTOs below is BioModels' own field name for the id
of a *referenced* entity — a PubMed id, a taxonomy or ontology term. A model's
own id is a `modelId`, not an accession.

BioModels serves camelCase JSON; these DTOs accept that and emit snake_case
like every other schema in this package.

Two upstream fields are deliberately dropped:

* ``description`` — usually the raw SBML ``<notes>`` XHTML blob rather than
  prose, carrying author-supplied ``<a href>`` markup. BioModels documents the
  field only as "string", so whether any given model returns markup or plain
  text cannot be relied on either way. ``publication.synopsis`` is documented
  plain text and is used instead; it is the source paper's abstract, so it is
  present only for models that cite one.
* contributor e-mail addresses — ``AuthorDTO`` in `schemas.registry` models
  authorship without them, and this endpoint is not a route for republishing
  harvested addresses.
"""

import re
from datetime import datetime
from typing import Any

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

# BioModels model ids are a letter prefix plus digits ("BIOMD0000000732",
# "MODEL2002170001", "BMID000000000001"). Ids reach us from CAIRNS, so they are
# matched against this before being interpolated into a request path.
_MODEL_ID_PATTERN = re.compile(r"^[A-Z]{3,10}[0-9]{4,20}$")


def normalize_model_id(value: str) -> str | None:
    """Return the canonical BioModels model id, or None if `value` isn't one."""
    candidate = value.strip().upper()
    return candidate if _MODEL_ID_PATTERN.match(candidate) else None


class _BioModelsDTO(BaseModel):
    # camelCase on the way in only.
    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_camel),
        populate_by_name=True,
        extra="ignore",
    )


class BioModelsFormatDTO(_BioModelsDTO):
    name: str = ""
    identifier: str = ""
    version: str = ""


class BioModelsTermDTO(_BioModelsDTO):
    """An ontology term: BioModels' `modellingApproach` and annotation shape."""

    accession: str = ""
    name: str = ""
    resource: str = ""
    uri: str = ""


class BioModelsAnnotationDTO(BioModelsTermDTO):
    # RDF qualifier the model asserts the term with, e.g. "bqbiol:hasTaxon".
    qualifier: str = ""


class BioModelsPublicationDTO(_BioModelsDTO):
    type: str = ""
    accession: str = ""
    journal: str = ""
    title: str = ""
    synopsis: str = ""


class BioModelsContributorDTO(_BioModelsDTO):
    name: str = ""
    orcid: str = ""
    affiliation: str = ""
    # Upstream keys `contributors` by role ("Curator", "Modeller"); the
    # flattening in BioModelsRecordDTO moves that key here.
    role: str = ""


class BioModelsFileDTO(_BioModelsDTO):
    name: str = ""
    description: str = ""
    file_size: int | None = None
    mime_type: str = ""


class BioModelsFilesDTO(_BioModelsDTO):
    main: list[BioModelsFileDTO] = Field(default_factory=list)
    additional: list[BioModelsFileDTO] = Field(default_factory=list)


class BioModelsRecordDTO(_BioModelsDTO):
    # Model id this record was fetched under, and its canonical web page.
    # Filled in by the client rather than parsed: `publication_id` is absent
    # on non-curated models, so the payload alone cannot identify itself.
    identifier: str = ""
    url: str = ""

    name: str = ""
    submission_id: str = ""
    publication_id: str = ""
    curation_status: str = ""
    first_published: datetime | None = None
    format: BioModelsFormatDTO | None = None
    modelling_approach: BioModelsTermDTO | None = None
    publication: BioModelsPublicationDTO | None = None
    contributors: list[BioModelsContributorDTO] = Field(default_factory=list)
    annotations: list[BioModelsAnnotationDTO] = Field(
        default_factory=list,
        validation_alias="modelLevelAnnotations",
    )
    files: BioModelsFilesDTO | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_contributors(cls, data: Any) -> Any:
        """Turn upstream's `{role: [contributor, ...]}` map into a flat list."""
        if not isinstance(data, dict):
            return data
        contributors = data.get("contributors")
        if not isinstance(contributors, dict):
            return data

        flattened: list[dict[str, Any]] = []
        for role, entries in contributors.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict):
                    flattened.append({**entry, "role": str(role)})
        return {**data, "contributors": flattened}
