from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Existing list schemas (backward compat) ──────────────────────────


class ModelListItem(BaseModel):
    id: str
    name: str
    resource_type: str
    location_uri: str
    execution_type: str | None = None
    version: str = ""
    status: str
    owner: str = ""
    description: str = ""
    created_at: datetime


class ModelListResponse(BaseModel):
    results: list[ModelListItem]


# ── Full-text search schemas ─────────────────────────────────────────

FilterOp = Literal["eq", "overlap", "contains", "gte", "lte"]
SortField = Literal["_score", "name", "created_at", "updated_at"]
SortOrder = Literal["asc", "desc"]


class SearchFilterDTO(BaseModel):
    field: str
    op: FilterOp
    value: Any  # str, list[str], or datetime string


class SearchSortDTO(BaseModel):
    field: SortField = "_score"
    order: SortOrder = "desc"


class SearchRequest(BaseModel):
    query: str | None = Field(default=None, description="Full-text search query")
    filters: list[SearchFilterDTO] = Field(default_factory=list)
    aggs: list[str] = Field(default_factory=list, description="Fields to aggregate")
    sort: SearchSortDTO = Field(default_factory=SearchSortDTO)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResultItem(BaseModel):
    id: str
    name: str
    resource_type: str
    location_uri: str
    description: str = ""
    version: str = ""
    status: str
    owner: str = ""
    execution_type: str | None = None
    organisms: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    modeling_scales: list[str] = Field(default_factory=list)
    format_tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    score: float | None = None


class AggBucketDTO(BaseModel):
    key: str
    count: int


class AggResultDTO(BaseModel):
    buckets: list[AggBucketDTO]


class SearchResponse(BaseModel):
    total: int = Field(ge=0)
    results: list[SearchResultItem]
    aggs: dict[str, AggResultDTO] = Field(default_factory=dict)
