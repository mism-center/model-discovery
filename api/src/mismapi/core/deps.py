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

from collections.abc import Generator
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from mism_registry.backends.postgres import PostgresRegistry

from mismapi.core.container import AppContainer
from mismapi.core.settings import Settings
from mismapi.services.registry_service import RegistryService

if TYPE_CHECKING:
    from mismapi.auth.oidc_service import OIDCService
    from mismapi.auth.session import SessionStore
    from mismapi.auth.session_refresh import SessionRefresher
    from mismapi.auth.validator import AuthValidator
    from mismapi.clients.cairns_client import CairnsClient
    from mismapi.clients.execution_client import ExecutionClient
    from mismapi.clients.local_upload_client import LocalFileUploadClient
    from mismapi.clients.upload_client import UploadServiceClient
    from mismapi.services.upload_session_store_service import UploadSessionStoreService


def _get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


ContainerDep = Annotated[AppContainer, Depends(_get_container)]


def _get_settings(container: ContainerDep) -> Settings:
    return container.settings


def _get_session_store(container: ContainerDep) -> SessionStore:
    return container.session_store


def _get_upload_session_store_service(container: ContainerDep) -> UploadSessionStoreService:
    return container.upload_session_store_service


def _get_auth_validator(container: ContainerDep) -> AuthValidator:
    return container.auth_validator


def _get_oidc_service(container: ContainerDep) -> OIDCService:
    return container.oidc_service


def _get_session_refresher(container: ContainerDep) -> SessionRefresher:
    return container.session_refresher


def _get_upload_client(
    container: ContainerDep,
) -> UploadServiceClient | LocalFileUploadClient:
    return container.upload_client


def _get_execution_client(container: ContainerDep) -> ExecutionClient:
    return container.execution_client


def _get_cairns_client(container: ContainerDep) -> CairnsClient:
    return container.cairns_client


def _get_registry_service(
    container: ContainerDep,
) -> Generator[RegistryService, None, None]:
    """
    Open a per-request SQLAlchemy session and yield a RegistryService bound to it.

    The session is always closed on teardown; commits/rollbacks are the service's
    responsibility.
    """
    with container.open_session() as session:
        yield RegistryService(PostgresRegistry(session), session)


SettingsDep = Annotated[Settings, Depends(_get_settings)]
SessionStoreDep = Annotated["SessionStore", Depends(_get_session_store)]
UploadSessionStoreServiceDep = Annotated[
    "UploadSessionStoreService", Depends(_get_upload_session_store_service)
]
AuthValidatorDep = Annotated["AuthValidator", Depends(_get_auth_validator)]
OIDCServiceDep = Annotated["OIDCService", Depends(_get_oidc_service)]
SessionRefresherDep = Annotated["SessionRefresher", Depends(_get_session_refresher)]
UploadClientDep = Annotated[
    "UploadServiceClient | LocalFileUploadClient", Depends(_get_upload_client)
]
ExecutionClientDep = Annotated["ExecutionClient", Depends(_get_execution_client)]
CairnsClientDep = Annotated["CairnsClient", Depends(_get_cairns_client)]
RegistryServiceDep = Annotated[RegistryService, Depends(_get_registry_service)]
