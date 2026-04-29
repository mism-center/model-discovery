from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mism_registry.backends.postgres import create_session_factory

from mismapi.api.router import build_api_router
from mismapi.auth.base import build_auth_validator
from mismapi.clients.execution_client import ExecutionClient
from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.errors import register_exception_handlers
from mismapi.core.logging import configure_root_logger
from mismapi.core.service_resolver import EnvServiceResolver
from mismapi.core.settings import get_settings
from mismapi.middleware.request_context import RequestContextMiddleware

_DEV_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]


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

    app.state.execution_client = ExecutionClient(
        base_url=resolver.execution_service_url(),
        timeout_seconds=settings.execution_timeout_seconds,
        stub_upstream=settings.stub_upstream_services,
    )

    app.state.session_factory = create_session_factory(settings.database_url)

    yield

    await app.state.execution_client.close()
    await app.state.upload_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_root_logger(log_level=settings.log_level)

    # Pin Swagger/ReDoc/OpenAPI under the API prefix so a UI can own "/".
    api_prefix = settings.api_prefix.rstrip("/")
    app = FastAPI(
        title="MISM Gateway API",
        version="0.1.0",
        description="Gateway API for searching, uploading, and managing model assets.",
        lifespan=lifespan,
        docs_url=f"{api_prefix}/docs",
        redoc_url=f"{api_prefix}/redoc",
        openapi_url=f"{api_prefix}/openapi.json",
    )

    if settings.mism_env in ("local", "development"):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_DEV_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
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
