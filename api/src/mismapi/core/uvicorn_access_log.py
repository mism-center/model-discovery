from __future__ import annotations

import logging
from copy import copy
from typing import Literal
from urllib.parse import parse_qsl

from uvicorn.logging import AccessFormatter

from mismapi.core.settings import Settings

REDACT_PLACEHOLDER = "<redacted>"


class SkipHealthCheckAccessFilter(logging.Filter):
    """Drop uvicorn access lines for liveness/readiness probes (reduces log noise in Kubernetes)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.args, tuple) or len(record.args) < 3:
            return True
        path = str(record.args[2]).split("?", 1)[0].rstrip("/") or "/"
        return path != "/healthz"


def redact_request_path(full_path: str, *, production: bool) -> str:
    if not production:
        return full_path
    if "?" not in full_path:
        return full_path
    path_part, _, query = full_path.partition("?")
    if not query:
        return path_part
    pairs = parse_qsl(query, keep_blank_values=True)
    parts: list[str] = []
    for key, value in pairs:
        if value == "":
            parts.append(key)
        else:
            parts.append(f"{key}={REDACT_PLACEHOLDER}")
    return f"{path_part}?{'&'.join(parts)}"


class RedactedAccessFormatter(AccessFormatter):
    """Uvicorn access formatter; when production_mode is on, query values are omitted from logs."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        use_colors: bool | None = None,
        *,
        production_mode: bool = False,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, use_colors=use_colors)
        self._production_mode = production_mode

    def formatMessage(self, record: logging.LogRecord) -> str:
        recordcopy = copy(record)
        if not recordcopy.args:
            return super().formatMessage(recordcopy)
        client_addr, method, full_path, http_version, status_code = recordcopy.args
        safe_path = redact_request_path(str(full_path), production=self._production_mode)
        recordcopy.args = (client_addr, method, safe_path, http_version, status_code)
        return super().formatMessage(recordcopy)


def install_uvicorn_access_formatter(settings: Settings) -> None:
    """Swap Uvicorn access log formatters; ``production_mode`` redacts query parameter values."""
    log = logging.getLogger("uvicorn.access")
    default_fmt = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    for handler in list(log.handlers):
        old = handler.formatter
        use_colors: bool | None = None
        fmt = default_fmt
        if isinstance(old, RedactedAccessFormatter):
            if old._production_mode == settings.production_mode:
                continue
        if isinstance(old, logging.Formatter):
            use_colors = getattr(old, "use_colors", None)
            style = getattr(old, "_style", None)
            if style is not None and hasattr(style, "_fmt"):
                fmt = str(style._fmt)
        handler.formatter = RedactedAccessFormatter(
            fmt=fmt,
            use_colors=use_colors,
            production_mode=settings.production_mode,
        )
    skip_health = SkipHealthCheckAccessFilter()
    for handler in list(log.handlers):
        if not any(isinstance(f, SkipHealthCheckAccessFilter) for f in handler.filters):
            handler.addFilter(skip_health)
