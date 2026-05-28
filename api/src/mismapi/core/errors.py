import logging
from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger(__name__)

REQUEST_VALIDATION_DETAIL_TEMPLATE = "Request validation failed for field '{field}'."
UNKNOWN_VALIDATION_FIELD = "unknown field"


class APIError(Exception):
    status_code: int
    code: str
    detail: str

    def __init__(self, *, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


class ValidationFieldError(APIError):
    field: str

    def __init__(
        self, *, field: str, status_code: int = 400, code: str = "validation_error"
    ) -> None:
        self.field = field
        super().__init__(
            status_code=status_code,
            code=code,
            detail=REQUEST_VALIDATION_DETAIL_TEMPLATE.format(field=field),
        )


def _normalize_error_location(raw_location: object) -> list[str]:
    if not isinstance(raw_location, Sequence) or isinstance(raw_location, str):
        return []
    return [str(part) for part in raw_location]


def _summarize_request_validation(exc: RequestValidationError) -> ValidationFieldError:
    for error in exc.errors():
        location = _normalize_error_location(error.get("loc"))
        if location:
            return ValidationFieldError(field=location[-1])
    return ValidationFieldError(field=UNKNOWN_VALIDATION_FIELD)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        settings = getattr(request.app.state, "settings", None)
        production = bool(getattr(settings, "production_mode", False))

        log_level = logging.ERROR if exc.status_code >= 500 else logging.INFO
        logger.log(
            log_level,
            "api_error status=%s code=%s method=%s path=%s",
            exc.status_code,
            exc.code,
            request.method,
            request.url.path,
        )
        # Log the error detail in debug mode specifically
        if not production and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "api_error_detail code=%s detail=%s",
                exc.code,
                exc.detail,
            )

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
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        validation_error = _summarize_request_validation(exc)
        return await api_error_handler(request, validation_error)

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
        production = bool(getattr(settings, "production_mode", False))
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
