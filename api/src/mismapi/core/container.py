"""Application container wiring all long-lived collaborators.

The container is constructed once per app, during `lifespan`. Everything the
request path needs is reachable through this object; the container itself is
the single source of truth for app-scoped state (and the single thing stored
at `app.state.container`). Dependency providers in `mismapi.core.deps`
read from the container; nothing else should.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from mismapi.auth.factory import build_auth_validator
from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
from mismapi.auth.oidc_service import OIDCService
from mismapi.auth.session import RedisSessionStore, SessionStore
from mismapi.auth.session_refresh import SessionRefresher
from mismapi.clients.helx_execution_client import HelxExecutionClient
from mismapi.clients.upload_client import UploadServiceClient
from mismapi.core.config_validation import ensure_startup_config
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mismapi.auth.validator import AuthValidator

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class AppContainer:
    """Owns every app-scoped collaborator and knows how to tear them down."""

    settings: Settings
    redis: Redis
    session_store: SessionStore
    upload_client: UploadServiceClient
    helx_execution_client: HelxExecutionClient
    auth_validator: AuthValidator
    oidc_discovery_cache: OIDCDiscoveryCache
    oidc_service: OIDCService
    session_refresher: SessionRefresher
    _engine: Engine
    _session_factory: sessionmaker[Session]

    @contextmanager
    def open_session(self) -> Iterator[Session]:
        """
        Open a SQLAlchemy session and yield it.

        The one blessed way to get a `Session`. Commits/rollbacks remain the
        caller's responsibility; this only owns the session lifecycle.
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

        upload_client = UploadServiceClient(
            base_url=settings.upload_service_url,
            timeout_seconds=settings.upload_timeout_seconds,
            stub_upstream=settings.stub_upstream_services,
        )
        helx_execution_client = HelxExecutionClient(
            base_url=settings.helx_exec_platform_base_url or "http://localhost",
            timeout_seconds=settings.helx_exec_platform_timeout_seconds,
            stub_upstream=settings.stub_upstream_services,
        )

        redis_client: Redis = Redis.from_url(  # type: ignore[type-arg]
            settings.redis_url,
            decode_responses=False,
        )
        session_store: SessionStore = RedisSessionStore(
            redis=redis_client,
            session_ttl_seconds=settings.session_ttl_seconds,
        )

        oidc_discovery_cache = OIDCDiscoveryCache(settings=settings)
        auth_validator = build_auth_validator(
            settings=settings,
            discovery_cache=oidc_discovery_cache,
        )
        oidc_service = OIDCService(
            settings=settings,
            discovery=oidc_discovery_cache,
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
            upload_client=upload_client,
            helx_execution_client=helx_execution_client,
            auth_validator=auth_validator,
            oidc_discovery_cache=oidc_discovery_cache,
            oidc_service=oidc_service,
            session_refresher=session_refresher,
            _engine=engine,
            _session_factory=session_factory,
        )

    async def prime(self) -> None:
        """Best-effort warm-up of collaborators whose first-use latency hurts.

        Currently primes the OIDC discovery cache in OIDC mode. Failures are logged and
        swallowed — the first real request will retry.
        """
        if self.settings.auth_mode != "oidc":
            return
        try:
            await self.oidc_discovery_cache.get()
        except APIError:
            logger.warning("oidc_discovery_prime_failed")

    async def aclose(self) -> None:
        """Tear down every collaborator, best-effort. Errors are logged, never raised."""
        for name, close in (
            ("upload_client", self.upload_client.close),
            ("helx_execution_client", self.helx_execution_client.close),
            ("oidc_service", self.oidc_service.aclose),
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
