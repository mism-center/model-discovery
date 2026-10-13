from typing import Any

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MISM_SOURCE = "MISM_models"


class CairnsRecommendRequest(BaseModel):
    question: str = Field(
        min_length=1,
        description="Natural-language question about computational tools.",
    )
    chat_history: list[list[str]] = Field(
        default_factory=list,
        description="Prior turns as [[user, assistant], ...] for follow-ups.",
    )
    thread_id: str | None = Field(default=None, description="Optional conversation id.")


class _SchemaOrgDTO(BaseModel):
    # CAIRNS serves schema.org's camelCase; emitted snake_case like every other
    # schema in this package.
    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_camel),
        populate_by_name=True,
        extra="ignore",
    )


class CairnsTermDTO(_SchemaOrgDTO):
    """A schema.org DefinedTerm, e.g. an EDAM topic, operation or format."""

    name: str = ""
    identifier: str = ""
    url: str = ""
    in_defined_term_set: str = ""


class CairnsDataTermDTO(CairnsTermDTO):
    """An EDAM data type a tool consumes or produces, with its formats."""

    encoding_format: list[CairnsTermDTO] = Field(default_factory=list)


class CairnsCitationDTO(_SchemaOrgDTO):
    name: str = ""
    doi: str = ""
    pmid: str = ""
    abstract: str = ""


class CairnsToolMetadataDTO(_SchemaOrgDTO):
    """CAIRNS' schema.org ComputationalTool record for an evidence card."""

    identifier: str = Field(default="", description="The source's own id for the record.")
    name: str = ""
    description: str = ""
    url: str = ""
    version: str = ""
    license: str = ""
    application_category: list[str] = Field(default_factory=list)
    programming_language: list[str] = Field(default_factory=list)
    operating_system: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    topic_category: list[CairnsTermDTO] = Field(default_factory=list)
    feature_list: list[CairnsTermDTO] = Field(default_factory=list)
    input: list[CairnsDataTermDTO] = Field(default_factory=list)
    output: list[CairnsDataTermDTO] = Field(default_factory=list)
    citation: list[CairnsCitationDTO] = Field(default_factory=list)
    raw_metadata: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The source's own record, verbatim, so its shape varies by source. "
            "Absent for sources that provide none, such as ToolDB."
        ),
    )


class CairnsEvidenceCardDTO(BaseModel):
    tool_id: str
    name: str
    # "tooldb", "biomodels" or "MISM_models" today; left open because CAIRNS owns
    # the vocabulary.
    source: str
    score: float = 0.0
    snippet: str = ""
    why_matched: list[str] = Field(default_factory=list)
    url: str = ""
    metadata: CairnsToolMetadataDTO = Field(default_factory=CairnsToolMetadataDTO)
    mism_model_id: str | None = Field(
        default=None,
        description=(
            "This registry's model behind the card, or null if there is none the "
            "caller may see: for a MISM card the model it names, for any other an "
            "import of the same record."
        ),
    )


class CairnsRecommendResponse(BaseModel):
    answer: str
    evidence: list[CairnsEvidenceCardDTO] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
