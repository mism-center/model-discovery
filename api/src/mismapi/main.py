from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mismapi.api.router import build_api_router
from mismapi.auth.base import build_auth_validator
from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.errors import register_exception_handlers
from mismapi.core.logging import configure_root_logger
from mismapi.core.service_resolver import EnvServiceResolver
from mismapi.core.settings import get_settings
from mismapi.middleware.request_context import RequestContextMiddleware
from mismapi.services.registry_service import RegistryService
from mism_registry.backends.postgres import create_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    resolver = EnvServiceResolver(settings=settings)

    app.state.settings = settings
    app.state.auth_validator = build_auth_validator(settings=settings)

    app.state.upload_client = UploadServiceClient(
        base_url=resolver.upload_service_url(),
        timeout_seconds=settings.upload_timeout_seconds,
        stub_upstream=settings.stub_upstream_services,
    )

    registry, session = create_registry(settings.database_url)
    app.state.registry_service = RegistryService(registry, session)

    yield

    app.state.registry_service.close()
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
