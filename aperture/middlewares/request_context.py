"""HTTP middleware for request context and access logs.

Example: a user gets a 404 response with X-Request-ID=request-1.
An operator can search logs with request-1 and find the matching request.
"""

from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response

from aperture.logger import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
NOSNIFF_HEADER = "X-Content-Type-Options"


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bind request context and log one line per HTTP request."""

    settings = getattr(request.app.state, "settings", None)
    service_name = getattr(settings, "service_name", "aperture")
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
    request.state.request_id = request_id

    # Start with a clean context so data from another request cannot leak.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service_name=service_name,
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    started_at = perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((perf_counter() - started_at) * 1000, 2)

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[NOSNIFF_HEADER] = "nosniff"

        structlog.contextvars.bind_contextvars(
            status=response.status_code,
            duration_ms=duration_ms,
        )
        get_logger(__name__).info(
            "http request finished",
            service_name=service_name,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    finally:
        # Always clear the context when the request is finished.
        structlog.contextvars.clear_contextvars()
