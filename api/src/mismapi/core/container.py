"""
Application container wiring all long-lived collaborators.

The container is constructed once per app, during `lifespan`. Everything the
request path needs is reachable through this object; the container itself is
the single source of truth for app-scoped state (and the single thing stored
at `app.state.container`). Dependency providers in `mismapi.core.deps`
read from the container; nothing else should.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from mismapi.auth.factory import build_auth_validator
from mismapi.auth.oauth_registry import build_oauth_registry, get_oidc_client
from mismapi.auth.oidc_service import OIDCService
from mismapi.auth.session import RedisSessionStore, SessionStore
from mismapi.auth.session_refresh import SessionRefresher
from mismapi.clients.execution_client import ExecutionClient
from mismapi.clients.local_upload_client import LocalFileUploadClient
from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.config_validation import ensure_startup_config
from mismapi.core.settings import Settings
from mismapi.services.upload_session_store_service import UploadSessionStoreService

if TYPE_CHECKING:
    from authlib.integrations.starlette_client import StarletteOAuth2App
    from sqlalchemy.orm import Session

    from mismapi.auth.validator import AuthValidator

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class AppContainer:
    """Owns every app-scoped collaborator and knows how to tear them down."""

    settings: Settings
    redis: Redis
    session_store: SessionStore
    upload_session_store_service: UploadSessionStoreService
    # Either a real HTTP client (UploadServiceClient) or the local-disk
    # stand-in (LocalFileUploadClient) — selected via settings.upload_backend.
    # Both implement the same async protocol consumed by the upload route.
    upload_client: UploadServiceClient | LocalFileUploadClient
    execution_client: ExecutionClient
    auth_validator: AuthValidator
    oidc_client: StarletteOAuth2App
    oidc_service: OIDCService
    session_refresher: SessionRefresher
    _engine: Engine
    _session_factory: sessionmaker[Session]

    @contextmanager
    def open_session(self) -> Generator[Session]:
        """
        Open a SQLAlchemy session and yield it.
        """
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    @classmethod
    def build(cls, settings: Settings) -> AppContainer:
        ensure_startup_config(settings)

        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        session_factory: sessionmaker[Session] = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            future=True,
        )

        # Upload backend: filesystem PVC (default while no upload service
        # exists) or remote HTTP upload service. Both expose the same async
        # protocol so the upload endpoint is backend-agnostic.
        upload_client: UploadServiceClient | LocalFileUploadClient
        if settings.upload_backend == "local":
            upload_client = LocalFileUploadClient(
                mount_path=settings.irods_mount_path,
                stub_upstream=settings.stub_upstream_services,
            )
        else:
            upload_client = UploadServiceClient(
                base_url=settings.upload_service_url,
                timeout_seconds=settings.upload_timeout_seconds,
                stub_upstream=settings.stub_upstream_services,
            )

        execution_client = ExecutionClient(
            base_url=settings.execution_api_url,
            timeout_seconds=settings.execution_timeout_seconds,
            stub_upstream=settings.stub_upstream_services,
        )

        redis_client: Redis = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
            settings.redis_url,
            decode_responses=False,
        )
        redis_session_store = RedisSessionStore(
            redis=redis_client,
            session_ttl_seconds=settings.session_ttl_seconds,
        )
        session_store: SessionStore = redis_session_store
        upload_session_store_service = UploadSessionStoreService(
            redis=redis_client,
            upload_token_ttl_seconds=settings.upload_token_ttl_seconds,
            tus_upload_ttl_seconds=settings.tus_upload_ttl_seconds,
        )

        oidc_client = get_oidc_client(build_oauth_registry(settings))
        oidc_service = OIDCService(settings=settings, client=oidc_client)
        auth_validator = build_auth_validator(
            settings=settings,
            oidc_service=oidc_service,
        )
        session_refresher = SessionRefresher(
            settings=settings,
            session_store=session_store,
            oidc_service=oidc_service,
        )

        return cls(
            settings=settings,
            redis=redis_client,
            session_store=session_store,
            upload_session_store_service=upload_session_store_service,
            upload_client=upload_client,
            execution_client=execution_client,
            auth_validator=auth_validator,
            oidc_client=oidc_client,
            oidc_service=oidc_service,
            session_refresher=session_refresher,
            _engine=engine,
            _session_factory=session_factory,
        )

    async def prime(self) -> None:
        """Best-effort warm-up of collaborators whose first-use latency hurts.

        Failures are logged and swallowed — the first real request will retry.
        """
        try:
            if self.settings.disable_auth:
                return
            await self.oidc_service.prime_metadata()
        except Exception as exc:
            logger.exception("oidc_discovery_prime_failed error=%s", exc)

    async def aclose(self) -> None:
        """Tear down every collaborator, best-effort. Errors are logged, never raised."""
        for name, close in (
            ("upload_client", self.upload_client.close),
            ("execution_client", self.execution_client.close),
            ("redis", self.redis.aclose),
        ):
            try:
                await close()
            except Exception:
                logger.exception("container_close_failed component=%s", name)

        try:
            self._engine.dispose()
        except Exception:
            logger.exception("container_close_failed component=engine")
