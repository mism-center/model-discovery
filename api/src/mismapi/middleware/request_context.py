import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mismapi.core.logging import request_id_context

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        log_this_request = self._should_log_request(request)
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.headers["x-request-id"] = request_id
            if log_this_request:
                logger.info(
                    "request_completed method=%s path=%s status_code=%s duration_ms=%.2f",
                    request.method,
                    request.url.path,
                    response.status_code,
                    elapsed_ms,
                )
            return response
        finally:
            request_id_context.reset(token)

    def _should_log_request(self, request: Request) -> bool:
        """
        Returns True if the request should be logged. If you need any specific paths to be excluded
        from logging, change this method.
        """
        return request.url.path.rstrip("/") != "/healthz"
