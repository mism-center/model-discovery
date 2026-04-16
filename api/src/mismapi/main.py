from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from mismapi.api.router import build_api_router
from mismapi.auth.base import build_auth_validator
from mismapi.auth.oidc import OIDCDiscoveryLoader
from mismapi.auth.session import RedisSessionStore
from mismapi.clients.helx_execution_client import HelxExecutionClient
from mismapi.clients.search_client import SearchServiceClient
from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.errors import register_exception_handlers
from mismapi.core.logging import configure_root_logger
from mismapi.core.service_resolver import EnvServiceResolver
from mismapi.core.settings import get_settings
from mismapi.core.uvicorn_access_log import install_uvicorn_access_formatter
from mismapi.middleware.request_context import RequestContextMiddleware


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
    helx_exec_platform_base_url = settings.helx_exec_platform_base_url.strip() or "http://localhost"
    app.state.helx_execution_client = HelxExecutionClient(
        base_url=helx_exec_platform_base_url,
        timeout_seconds=settings.helx_exec_platform_timeout_seconds,
        stub_upstream=settings.stub_upstream_services,
    )
    app.state.auth_validator = build_auth_validator(settings=settings)

    redis_client: Redis = Redis.from_url(  # type: ignore[type-arg]
        settings.redis_url,
        decode_responses=False,
    )
    app.state.redis = redis_client
    app.state.session_store = RedisSessionStore(
        redis=redis_client,
        session_ttl_seconds=settings.session_ttl_seconds,
    )
    app.state.oidc_discovery_loader = OIDCDiscoveryLoader(settings=settings)

    yield

    await app.state.search_client.close()
    await app.state.upload_client.close()
    await app.state.helx_execution_client.close()
    await redis_client.aclose()


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
