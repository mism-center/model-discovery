from pydantic import BaseModel, Field

from mismapi.schemas.common import CustomMetadata


class SearchRequestParams(BaseModel):
    q: str
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResultItem(BaseModel):
    id: str
    type: str
    name: str
    description: str | None = None
    score: float | None = None
    metadata: CustomMetadata = Field(default_factory=dict)


class SearchResponse(BaseModel):
    total: int = Field(ge=0)
    results: list[SearchResultItem]
