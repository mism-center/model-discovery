from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mismapi.api.router import build_api_router
from mismapi.core.container import AppContainer
from mismapi.core.errors import register_exception_handlers
from mismapi.core.logging import configure_root_logger
from mismapi.core.settings import Settings, get_settings
from mismapi.core.uvicorn_access_log import install_uvicorn_access_formatter
from mismapi.middleware.request_context import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Build the FastAPI app with the given settings.

    `settings` is optional so production callers stay on the cached
    `get_settings()` instance. Tests pass a fresh `Settings(...)` here to
    avoid mutating `os.environ` and bouncing the settings cache (by default,
    `get_settings()` returns the cached instance).
    """
    resolved_settings = settings if settings is not None else get_settings()
    configure_root_logger(log_level=resolved_settings.log_level)
    install_uvicorn_access_formatter(resolved_settings)

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = AppContainer.build(resolved_settings)
        app.state.container = container
        await container.prime()

        try:
            yield
        finally:
            await container.aclose()

    app = FastAPI(
        title="MISM Gateway API",
        version="0.1.0",
        description="Gateway API for searching, uploading, and managing model assets.",
        lifespan=_lifespan,
    )

    app.state.settings = resolved_settings
    app.add_middleware(RequestContextMiddleware)
    app.include_router(build_api_router())
    register_exception_handlers(app)

    @app.get("/healthz", tags=["System"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app: FastAPI = create_app()
