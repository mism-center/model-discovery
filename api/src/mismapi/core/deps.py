"""Typed FastAPI dependency providers.

All request-time access to app-scoped collaborators goes through this module.
Handlers and helpers should never read ``request.app.state`` directly; they
declare a typed ``Annotated[..., Depends(...)]`` parameter from here instead.
This keeps the dependency graph visible to the type checker and to FastAPI's
``dependency_overrides`` machinery, so tests can swap any collaborator without
monkeypatching ``app.state``.

The single blessed entry point into ``app.state`` is :func:`_get_container`;
every other provider derives from it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from fastapi import Depends, Request

from mismapi.core.container import AppContainer
from mismapi.core.errors import APIError
from mismapi.core.settings import Settings

if TYPE_CHECKING:
    from mismapi.auth.oidc_discovery import OIDCDiscoveryCache
    from mismapi.auth.oidc_service import OIDCService
    from mismapi.auth.session import SessionStore
    from mismapi.auth.session_refresh import SessionRefresher
    from mismapi.auth.validator import AuthValidator, OIDCValidator
    from mismapi.clients.helx_execution_client import HelxExecutionClient
    from mismapi.clients.search_client import SearchServiceClient
    from mismapi.clients.upload_client import UploadServiceClient


def _get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


ContainerDep = Annotated[AppContainer, Depends(_get_container)]


def _get_settings(container: ContainerDep) -> Settings:
    return container.settings


def _get_session_store(container: ContainerDep) -> SessionStore:
    return container.session_store


def _get_auth_validator(container: ContainerDep) -> AuthValidator:
    return container.auth_validator


def _get_oidc_validator(container: ContainerDep) -> OIDCValidator:
    """Resolve the active validator as an ``OIDCValidator`` or 503 in non-OIDC mode.

    In OIDC mode the container always wires an ``OIDCAuthValidator``, which
    structurally satisfies :class:`mismapi.auth.base.OIDCValidator`. The
    ``settings.auth_mode`` gate is the runtime guarantee; handlers can then
    call ``verify_identity`` without ``isinstance``-branching on the concrete
    class.
    """
    if container.settings.auth_mode != "oidc":
        raise APIError(
            status_code=503,
            code="oidc_validator_required",
            detail="Operation requires OIDC authentication mode.",
        )
    return cast("OIDCValidator", container.auth_validator)


def _get_oidc_discovery_cache(container: ContainerDep) -> OIDCDiscoveryCache:
    return container.oidc_discovery_cache


def _get_oidc_service(container: ContainerDep) -> OIDCService:
    return container.oidc_service


def _get_session_refresher(container: ContainerDep) -> SessionRefresher:
    return container.session_refresher


def _get_search_client(container: ContainerDep) -> SearchServiceClient:
    return container.search_client


def _get_upload_client(container: ContainerDep) -> UploadServiceClient:
    return container.upload_client


def _get_helx_execution_client(container: ContainerDep) -> HelxExecutionClient:
    return container.helx_execution_client


SettingsDep = Annotated[Settings, Depends(_get_settings)]
SessionStoreDep = Annotated["SessionStore", Depends(_get_session_store)]
AuthValidatorDep = Annotated["AuthValidator", Depends(_get_auth_validator)]
OIDCValidatorDep = Annotated["OIDCValidator", Depends(_get_oidc_validator)]
OIDCDiscoveryCacheDep = Annotated["OIDCDiscoveryCache", Depends(_get_oidc_discovery_cache)]
OIDCServiceDep = Annotated["OIDCService", Depends(_get_oidc_service)]
SessionRefresherDep = Annotated["SessionRefresher", Depends(_get_session_refresher)]
SearchClientDep = Annotated["SearchServiceClient", Depends(_get_search_client)]
UploadClientDep = Annotated["UploadServiceClient", Depends(_get_upload_client)]
HelxExecutionClientDep = Annotated["HelxExecutionClient", Depends(_get_helx_execution_client)]
