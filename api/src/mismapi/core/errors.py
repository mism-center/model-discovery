import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from mismapi.core.settings import Settings
from mismapi.schemas.common import MODEL_ID_PATTERN

logger = logging.getLogger(__name__)

MODEL_ID_FORMAT_HINT = "Path parameter 'model_id' must be exactly 12 alphanumeric characters."


class ValidationFieldError(TypedDict, total=False):
    field: str
    location: list[str]
    type: str
    message: str


@dataclass(slots=True)
class APIError(Exception):
    status_code: int
    code: str
    detail: str


def _normalize_error_location(raw_location: object) -> list[str]:
    if not isinstance(raw_location, Sequence) or isinstance(raw_location, str):
        return []
    return [str(part) for part in raw_location]


def _is_model_id_format_error(*, location: list[str], error_type: str, context: object) -> bool:
    if not isinstance(context, Mapping):
        return False
    context_mapping = cast(Mapping[str, object], context)
    return (
        len(location) >= 2
        and location[0] == "path"
        and location[-1] == "model_id"
        and error_type == "string_pattern_mismatch"
        and context_mapping.get("pattern") == MODEL_ID_PATTERN
    )


def _summarize_request_validation(
    exc: RequestValidationError,
) -> tuple[str, list[ValidationFieldError]]:
    field_errors: list[ValidationFieldError] = []
    saw_model_id_format_error = False

    for error in exc.errors():
        location = _normalize_error_location(error.get("loc"))
        error_type = str(error.get("type", "validation_error"))
        context = error.get("ctx")
        message = str(error.get("msg", "Invalid request value."))

        if _is_model_id_format_error(
            location=location,
            error_type=error_type,
            context=context,
        ):
            message = MODEL_ID_FORMAT_HINT
            saw_model_id_format_error = True

        item: ValidationFieldError = {
            "location": location,
            "type": error_type,
            "message": message,
        }
        if location:
            item["field"] = location[-1]
        field_errors.append(item)

    detail = MODEL_ID_FORMAT_HINT if saw_model_id_format_error else "Request validation failed."
    return detail, field_errors


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "detail": exc.detail,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        detail, field_errors = _summarize_request_validation(exc)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "detail": detail,
                    "fields": field_errors,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Log tracebacks for bugs and unexpected failures; still return a 500 body."""
        logger.exception(
            "unhandled_exception method=%s path=%s exc_type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc_info=True,
            stack_info=True,
        )
        settings = getattr(request.app.state, "settings", None)
        production = isinstance(settings, Settings) and settings.production_mode
        detail = (
            "An unexpected error occurred."
            if production
            else (str(exc) if str(exc) else type(exc).__name__)
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "detail": detail,
                },
            },
        )
