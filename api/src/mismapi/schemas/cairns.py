from pydantic import BaseModel, Field


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


class CairnsRecommendResponse(BaseModel):
    answer: str
    evidence: list[CairnsEvidenceCardDTO] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
