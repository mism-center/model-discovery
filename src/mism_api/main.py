from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mism_api.api.router import build_api_router
from mism_api.auth.base import build_auth_validator
from mism_api.clients.search_client import SearchServiceClient
from mism_api.clients.upload_client import UploadServiceClient
from mism_api.core.errors import register_exception_handlers
from mism_api.core.logging import configure_root_logger
from mism_api.core.service_resolver import EnvServiceResolver
from mism_api.core.settings import get_settings
from mism_api.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    resolver = EnvServiceResolver(settings=settings)

    app.state.settings = settings
    app.state.search_client = SearchServiceClient(
        base_url=resolver.search_service_url(),
        timeout_seconds=settings.search_timeout_seconds,
        stub_upstream=settings.stub_upstream_services,
    )
    app.state.upload_client = UploadServiceClient(
        base_url=resolver.upload_service_url(),
        timeout_seconds=settings.upload_timeout_seconds,
        stub_upstream=settings.stub_upstream_services,
    )
    app.state.auth_validator = build_auth_validator(settings=settings)
    yield
    await app.state.search_client.close()
    await app.state.upload_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_root_logger(log_level=settings.log_level)

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
