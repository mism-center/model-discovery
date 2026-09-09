from pydantic import BaseModel, Field

from mismapi.schemas.biomodels import BioModelsRecordDTO, normalize_model_id

BIOMODELS_SOURCE = "biomodels"
_BIOMODELS_TOOL_ID_PREFIX = "biomodels_"


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


class CairnsEvidenceCardDTO(BaseModel):
    tool_id: str
    name: str
    # "tooldb" or "biomodels" today; left open because CAIRNS owns the vocabulary.
    source: str
    score: float = 0.0
    snippet: str = ""
    why_matched: list[str] = Field(default_factory=list)
    url: str = ""
    # Populated iff `source == "biomodels"`
    biomodels: BioModelsRecordDTO | None = Field(
        default=None,
        description="Metadata resolved from the BioModels repository.",
    )

    @property
    def biomodels_model_id(self) -> str | None:
        """BioModels model id this card refers to, or None if it isn't one.

        CAIRNS embeds the id in `tool_id`, prefixed by its source
        ("biomodels_biomd0000000732" -> "BIOMD0000000732").
        """
        if self.source.strip().lower() != BIOMODELS_SOURCE:
            return None

        raw = self.tool_id.strip()
        if raw.lower().startswith(_BIOMODELS_TOOL_ID_PREFIX):
            raw = raw[len(_BIOMODELS_TOOL_ID_PREFIX) :]
        return normalize_model_id(raw)


class CairnsRecommendResponse(BaseModel):
    answer: str
    evidence: list[CairnsEvidenceCardDTO] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
