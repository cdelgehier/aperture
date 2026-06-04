"""Tests for API key authentication."""

from unittest.mock import patch

from fastapi import Request, Response
from fastapi.testclient import TestClient

from aperture.main import create_app
from aperture.middlewares.auth import api_key_auth_middleware
from aperture.settings import Settings


def test_auth_off_allows_private_routes() -> None:
    """Auth off allows requests without an API key."""

    settings = Settings(auth_mode="off")

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/admin/plugins")

    assert response.status_code == 200


def test_api_key_auth_skips_public_paths() -> None:
    """Public paths do not require an API key."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})

    with TestClient(create_app(settings)) as client:
        response = client.get("/livez")

    assert response.status_code == 200


def test_api_key_auth_skips_wildcard_paths() -> None:
    """Wildcard skip paths skip a route group."""

    settings = Settings(
        auth_mode="api_key",
        api_keys={"client": "secret"},
        auth_skip_paths=["/api/v1/admin/*"],
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/admin/plugins")

    assert response.status_code == 200


def test_api_key_auth_wildcard_does_not_match_partial_prefix() -> None:
    """Wildcard skip paths do not match similar path names."""

    settings = Settings(
        auth_mode="api_key",
        api_keys={"client": "secret"},
        auth_skip_paths=["/api/v1/demo/*"],
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/demolition")

    assert response.status_code == 401


def test_api_key_auth_wildcard_matches_prefix_itself() -> None:
    """Wildcard skip paths also skip the prefix without a trailing slash."""

    settings = Settings(
        auth_mode="api_key",
        api_keys={"client": "secret"},
        auth_skip_paths=["/api/v1/whoami/*"],
    )
    app = create_app(settings)

    @app.get("/api/v1/whoami")
    async def whoami() -> dict[str, str]:
        """Return one public response for the wildcard test."""

        return {"status": "public"}

    with TestClient(app) as client:
        response = client.get("/api/v1/whoami")

    assert response.status_code == 200


def test_api_key_auth_rejects_missing_key() -> None:
    """Missing API key returns Problem Details."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/admin/plugins",
            headers={"X-Request-ID": "request-1"},
        )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Missing API key.",
        "request_id": "request-1",
    }


def test_api_key_auth_rejects_invalid_key() -> None:
    """Invalid API key returns Problem Details."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/admin/plugins",
            headers={"X-API-Key": "wrong", "X-Request-ID": "request-1"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key."
    assert response.json()["request_id"] == "request-1"


async def test_api_key_auth_uses_header_request_id_without_request_context() -> None:
    """Auth errors can use request id header when request context is absent."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})
    app = create_app(settings)
    app.state.settings = settings
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/private",
            "headers": [(b"x-request-id", b"header-only")],
            "app": app,
        }
    )

    async def call_next(_: Request) -> Response:
        """The auth middleware should stop before the route."""

        raise AssertionError("call_next should not be called")

    response = await api_key_auth_middleware(request, call_next)

    assert response.status_code == 401
    assert b'"request_id":"header-only"' in response.body


def test_api_key_auth_accepts_valid_key() -> None:
    """Valid API key allows private routes."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/admin/plugins",
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 200


def test_api_key_auth_uses_custom_header() -> None:
    """API key auth can read a custom header."""

    settings = Settings(
        auth_mode="api_key",
        api_keys={"client": "secret"},
        api_key_header="X-Aperture-Key",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/admin/plugins",
            headers={"X-Aperture-Key": "secret"},
        )

    assert response.status_code == 200


def test_api_key_auth_binds_authenticated_service_to_request_state() -> None:
    """Valid API key stores the resolved service on request state."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})
    app = create_app(settings)

    @app.get("/api/v1/whoami")
    async def whoami(request: Request) -> dict[str, str]:
        """Return the service stored by the auth middleware."""

        service = request.state.authenticated_service
        return {"service_name": service.service_name}

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/whoami",
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"service_name": "client"}


def test_api_key_auth_binds_authenticated_service_to_logs() -> None:
    """Valid API key binds the resolved service name into logs."""

    settings = Settings(auth_mode="api_key", api_keys={"client": "secret"})

    with (
        patch(
            "aperture.middlewares.auth.structlog.contextvars.bind_contextvars"
        ) as bind,
        TestClient(create_app(settings)) as client,
    ):
        response = client.get(
            "/api/v1/admin/plugins",
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 200
    assert any(call.kwargs == {"service_name": "client"} for call in bind.mock_calls)


def test_api_key_auth_uses_constant_time_comparison() -> None:
    """API keys are compared with hmac.compare_digest."""

    settings = Settings(
        auth_mode="api_key",
        api_keys={
            "client-a": "secret-a",
            "client-b": "secret-b",
        },
    )

    with (
        patch(
            "aperture.middlewares.auth.compare_digest",
            side_effect=[False, True],
        ) as compare_digest,
        TestClient(create_app(settings)) as client,
    ):
        response = client.get(
            "/api/v1/admin/plugins",
            headers={"X-API-Key": "secret-b"},
        )

    assert response.status_code == 200
    assert compare_digest.call_count == 2
