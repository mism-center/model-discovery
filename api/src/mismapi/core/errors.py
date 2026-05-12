import logging
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from mismapi.core.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class APIError(Exception):
    status_code: int
    code: str
    detail: str


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
