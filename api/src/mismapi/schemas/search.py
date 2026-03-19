from pydantic import BaseModel, Field

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | dict[str, "JsonValue"] | list["JsonValue"]
type JsonObject = dict[str, JsonValue]


class SearchRequestParams(BaseModel):
    q: str
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResultItem(BaseModel):
    data: JsonObject
    score: float


class SearchResponse(BaseModel):
    total: int = Field(ge=0)
    results: list[SearchResultItem]
