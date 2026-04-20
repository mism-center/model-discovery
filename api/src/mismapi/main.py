from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mismapi.api.router import build_api_router
from mismapi.core.container import AppContainer
from mismapi.core.errors import register_exception_handlers
from mismapi.core.logging import configure_root_logger
from mismapi.core.settings import get_settings
from mismapi.core.uvicorn_access_log import install_uvicorn_access_formatter
from mismapi.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    container = AppContainer.build(settings)
    app.state.container = container
    await container.prime()

    try:
        yield
    finally:
        await container.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_root_logger(log_level=settings.log_level)
    install_uvicorn_access_formatter(settings)

    app = FastAPI(
        title="MISM Gateway API",
        version="0.1.0",
        description="Gateway API for searching, uploading, and managing model assets.",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.include_router(build_api_router())
    register_exception_handlers(app)

    @app.get("/healthz", tags=["System"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app: FastAPI = create_app()
