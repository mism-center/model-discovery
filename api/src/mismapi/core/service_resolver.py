from dataclasses import dataclass
from typing import Protocol

from mismapi.core.settings import Settings


class ServiceResolver(Protocol):
    def upload_service_url(self) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class EnvServiceResolver:
    settings: Settings

    def upload_service_url(self) -> str:
        return self.settings.upload_service_url.rstrip("/")
