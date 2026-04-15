import logging

import pytest
from uvicorn.logging import AccessFormatter

from mismapi.core.settings import Settings
from mismapi.core.uvicorn_access_log import (
    RedactedAccessFormatter,
    install_uvicorn_access_formatter,
    redact_request_path,
)


@pytest.mark.parametrize(
    ("full_path", "production", "expected"),
    [
        ("/api/v1/models", False, "/api/v1/models"),
        ("/api/v1/models", True, "/api/v1/models"),
        ("/api/foo?code=secret&state=abc", False, "/api/foo?code=secret&state=abc"),
        ("/api/foo?code=secret&state=abc", True, "/api/foo?code=<redacted>&state=<redacted>"),
        ("/path?", True, "/path"),
        ("/path?empty=", True, "/path?empty"),
        ("/path?a=1&b", True, "/path?a=<redacted>&b"),
    ],
)
def test_redact_request_path(full_path: str, production: bool, expected: str) -> None:
    assert redact_request_path(full_path, production=production) == expected


def test_redacted_access_formatter_production_hides_query_values() -> None:
    fmt = RedactedAccessFormatter(
        fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        use_colors=False,
        production_mode=True,
    )
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %s',
        args=("127.0.0.1:1", "GET", "/cb?code=topsecret&foo=bar", "1.1", 302),
        exc_info=None,
    )
    line = fmt.format(record)
    assert "topsecret" not in line
    assert "bar" not in line
    assert "<redacted>" in line


def test_redacted_access_formatter_non_production_shows_values() -> None:
    fmt = RedactedAccessFormatter(
        fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        use_colors=False,
        production_mode=False,
    )
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %s',
        args=("127.0.0.1:1", "GET", "/cb?code=visible", "1.1", 302),
        exc_info=None,
    )
    line = fmt.format(record)
    assert "visible" in line


def test_install_uvicorn_access_formatter_replaces_handler() -> None:
    log = logging.getLogger("uvicorn.access")
    old_handlers = list(log.handlers)
    handler = logging.StreamHandler()
    handler.setFormatter(
        AccessFormatter(
            fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            use_colors=False,
        )
    )
    log.addHandler(handler)
    try:
        settings = Settings()
        settings.production_mode = True
        install_uvicorn_access_formatter(settings)
        assert isinstance(handler.formatter, RedactedAccessFormatter)
        record = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='%s - "%s %s HTTP/%s" %s',
            args=("127.0.0.1:1", "GET", "/r?q=secret", "1.1", 200),
            exc_info=None,
        )
        line = handler.formatter.format(record)
        assert "secret" not in line
    finally:
        log.removeHandler(handler)
        for h in old_handlers:
            log.addHandler(h)
