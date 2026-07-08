import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger(__name__)

REQUEST_VALIDATION_DETAIL_TEMPLATE = "Request validation failed for field '{field}'."
UNKNOWN_VALIDATION_FIELD = "unknown field"
UNPROCESSABLE_VALIDATION_ERROR_TYPES = {"enum", "literal_error"}

# Reusable OpenAPI component describing the JSON body every APIError produces
# (see ``api_error_handler`` below): ``{"error": {"code": ..., "detail": ...}}``.
# Registered once under ``components.schemas`` so responses can $ref it instead
# of inlining the shape.
ERROR_RESPONSE_SCHEMA_NAME = "ErrorResponse"
ERROR_RESPONSE_SCHEMA: dict[str, Any] = {
    "title": ERROR_RESPONSE_SCHEMA_NAME,
    "type": "object",
    "properties": {
        "error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "detail": {"type": "string"},
            },
            "required": ["code", "detail"],
        },
    },
    "required": ["error"],
}


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
    status_code = 400
    for error in exc.errors():
        if error.get("type") in UNPROCESSABLE_VALIDATION_ERROR_TYPES:
            status_code = 422
            break

    for error in exc.errors():
        location = _normalize_error_location(error.get("loc"))
        if location:
            return ValidationFieldError(field=location[-1], status_code=status_code)
    return ValidationFieldError(field=UNKNOWN_VALIDATION_FIELD, status_code=status_code)


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


def _route_has_dependency(route: Any, target: Any) -> bool:
    """True if ``route``'s flattened dependency tree calls ``target``.

    FastAPI records every dependency (including transitive ones) on a route's
    ``dependant``. We walk it so a route that depends on ``require_principal``
    — directly or via ``AuthenticatedPrincipalDep`` — is detected without the
    route having to opt in.
    """
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return False

    seen: set[int] = set()
    stack = [dependant]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if getattr(current, "call", None) is target:
            return True
        stack.extend(getattr(current, "dependencies", []))
    return False


def install_openapi_customizations(app: FastAPI) -> None:
    """Make auth-required routes self-document their 401 in the OpenAPI schema.

    Rather than every authenticated path operation repeating ``responses={401:
    ...}``, we inject the 401 automatically for any route whose dependency tree
    includes ``require_principal``. New authenticated endpoints inherit the
    documented 401 for free — the requirement (a principal) and its documented
    failure (401) stay in lockstep.
    """
    # Imported here to avoid a circular import: mismapi.auth.base imports from
    # mismapi.core.* at module load.
    from fastapi.openapi.utils import get_openapi

    from mismapi.auth.base import require_principal

    error_ref = f"#/components/schemas/{ERROR_RESPONSE_SCHEMA_NAME}"
    unauthorized_response = {
        "description": "Authentication is required and was missing or invalid.",
        "content": {"application/json": {"schema": {"$ref": error_ref}}},
    }

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("schemas", {})[
            ERROR_RESPONSE_SCHEMA_NAME
        ] = ERROR_RESPONSE_SCHEMA

        paths = schema.get("paths", {})
        for route in app.routes:
            if not _route_has_dependency(route, require_principal):
                continue
            path_item = paths.get(getattr(route, "path_format", None) or route.path)
            if not path_item:
                continue
            for method in (m.lower() for m in getattr(route, "methods", set())):
                operation = path_item.get(method)
                if operation is None:
                    continue
                operation.setdefault("responses", {}).setdefault("401", unauthorized_response)

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
