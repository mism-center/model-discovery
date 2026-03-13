from typing import Any, Self

import httpx
from pydantic import BaseModel, ValidationError

from core.errors import APIError


# TODO: Intentionally retained for future standardization of API response
# deserialization/validation error mapping. Not currently used by models.
class APIErrorBehaviorModel(BaseModel):
    status_code: int
    code: str
    detail: str
    error_cls: type = APIError


# TODO: Intentionally retained for future standardization of API response
# deserialization/validation error mapping. Not currently used by models.
class APIModel(BaseModel):
    error_behavior: APIErrorBehaviorModel

    @classmethod
    def model_validate_or_error(
        cls,
        obj: Any,
        error_behavior: APIErrorBehaviorModel | None = None,
    ) -> Self:
        error_behavior = error_behavior or cls.error_behavior
        try:
            return cls.model_validate(obj)
        except ValidationError as exc:
            raise error_behavior.error_cls(
                status_code=error_behavior.status_code,
                code=error_behavior.code,
                detail=error_behavior.detail,
            ) from exc

    @classmethod
    def deserialize_response_or_error(
        cls,
        response: httpx.Response,
        error_behavior: APIErrorBehaviorModel | None = None,
    ) -> Self:
        try:
            payload = response.json()
        except ValueError as exc:
            error_behavior = error_behavior or cls.error_behavior
            raise error_behavior.error_cls(
                status_code=error_behavior.status_code,
                code=error_behavior.code,
                detail=error_behavior.detail,
            ) from exc

        return cls.model_validate_or_error(payload, error_behavior=error_behavior)
