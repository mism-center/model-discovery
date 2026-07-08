from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from mismapi.api.router import build_api_router
from mismapi.core.container import AppContainer
from mismapi.core.errors import install_openapi_customizations, register_exception_handlers
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

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = AppContainer.build(resolved_settings)
        app.state.container = container
        await container.prime()

        try:
            yield
        finally:
            await container.aclose()

    resolved_settings = settings if settings is not None else get_settings()
    configure_root_logger(log_level=resolved_settings.log_level)
    install_uvicorn_access_formatter(resolved_settings)

    # All API + auto-docs are mounted under this prefix so a UI can own "/".
    api_prefix = resolved_settings.api_prefix.rstrip("/")
    # Scope the OAuth-state cookie to the auth router. Tracks api_prefix so
    # the cookie path stays aligned with the auth router prefix in
    # `mismapi.api.router`. Cookie is only ever read by /{prefix}/auth/callback
    # (and written by /{prefix}/auth/login), no reason to ship it on every
    # authenticated API request.
    oauth_state_cookie_path = f"{api_prefix}/auth"

    app = FastAPI(
        title="MISM Gateway API",
        version="0.1.0",
        description="Gateway API for searching, uploading, and managing model assets.",
        lifespan=_lifespan,
        docs_url=f"{api_prefix}/docs",
        redoc_url=f"{api_prefix}/redoc",
        openapi_url=f"{api_prefix}/openapi.json",
    )

    app.state.settings = resolved_settings

    if not resolved_settings.disable_auth:
        app.add_middleware(
            SessionMiddleware,
            secret_key=resolved_settings.oidc_cookie_signing_secret,
            session_cookie=resolved_settings.oauth_state_cookie_name,
            max_age=resolved_settings.oauth_state_cookie_max_age_seconds,
            path=oauth_state_cookie_path,
            same_site="lax",
            https_only=resolved_settings.production_mode,
        )
    if not resolved_settings.production_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestContextMiddleware)
    if resolved_settings.deploy_type == "local":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(build_api_router())
    register_exception_handlers(app)
    install_openapi_customizations(app)

    @app.get("/healthz", tags=["System"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app: FastAPI = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
