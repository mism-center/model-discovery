from collections.abc import Generator

from fastapi import Request
from mism_registry.backends.postgres import PostgresRegistry
from sqlalchemy.orm import Session

from mismapi.services.registry_service import RegistryService


def get_registry_service(request: Request) -> Generator[RegistryService, None, None]:
    session: Session = request.app.state.session_factory()
    try:
        yield RegistryService(PostgresRegistry(session), session)
    finally:
        session.close()
