"""HTTP middleware for API key authentication."""

from collections.abc import Awaitable, Callable
from hmac import compare_digest

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from aperture.models.auth import AuthenticatedService
from aperture.models.problem_details import ProblemDetails
from aperture.settings import Settings


async def api_key_auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Protect routes with an API key when auth is enabled."""

    # The middleware reads settings from the app state.
    # This keeps the middleware small and easy to test.
    settings: Settings = request.app.state.settings

    # In local mode, or for public technical routes, we do not check any key.
    # Example: /livez and /readyz must stay usable by Kubernetes probes.
    if settings.auth_mode == "off" or _is_skip_path(request.url.path, settings):
        return await call_next(request)

    # The header name is configurable.
    # Default example: X-API-Key: my-secret-value
    service, error_detail = _authenticate_api_key(
        received_key=request.headers.get(settings.api_key_header),
        api_keys=settings.api_keys,
    )
    if service is None:
        # Request context middleware normally creates request.state.request_id.
        # This fallback keeps 401 errors useful even if middleware order changes.
        request_id = getattr(request.state, "request_id", None)
        if request_id is None:
            request_id = request.headers.get("X-Request-ID", "unknown")

        # Auth errors use RFC 7807 Problem Details like the global error handler.
        problem = ProblemDetails(
            title="Unauthorized",
            status=401,
            detail=error_detail or "Invalid API key.",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=401,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    # Store the matched service for later code.
    # A plugin could read it from request.state if it needs this identity.
    request.state.authenticated_service = service

    # Bind the real caller name in logs after auth succeeds.
    # This can replace the default app service_name for this request.
    structlog.contextvars.bind_contextvars(service_name=service.service_name)
    return await call_next(request)


def _is_skip_path(path: str, settings: Settings) -> bool:
    """Return true when a path does not need auth."""

    for skipped_path in settings.auth_skip_paths:
        # A trailing /* means "this path and every child path".
        # Example: /api/v1/demo/* matches /api/v1/demo and /api/v1/demo/fountains.
        if skipped_path.endswith("/*"):
            prefix = skipped_path.removesuffix("/*")
            if path == prefix or path.startswith(f"{prefix}/"):
                return True
            continue

        # Without /* we only accept the exact path.
        # Example: /docs matches /docs, but not /docs/custom.
        if path == skipped_path:
            return True
    return False


def _authenticate_api_key(
    *,
    received_key: str | None,
    api_keys: dict[str, str],
) -> tuple[AuthenticatedService | None, str | None]:
    """Return the matching service or an auth error detail."""

    if not received_key:
        return None, "Missing API key."

    matched_service: str | None = None
    for service_name, expected_key in api_keys.items():
        # compare_digest avoids leaking useful timing details.
        # It is safer than "received_key == expected_key" for secrets.
        if compare_digest(received_key, expected_key):
            matched_service = service_name

    if matched_service is None:
        return None, "Invalid API key."

    return AuthenticatedService(service_name=matched_service), None
