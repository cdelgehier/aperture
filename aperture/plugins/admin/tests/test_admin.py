"""Tests for the admin plugin."""

from fastapi.testclient import TestClient
from pydantic import RedisDsn

from aperture.main import create_app
from aperture.settings import Settings


def test_admin_lists_loaded_plugins() -> None:
    """The admin plugin lists loaded plugins as select items."""

    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/v1/admin/plugins")

    assert response.status_code == 200
    assert response.json() == [{"label": "admin - /admin", "value": "admin"}]


def test_admin_lists_api_routes() -> None:
    """The admin plugin lists API routes as select items."""

    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/v1/admin/routes")

    assert response.status_code == 200
    assert {
        "label": "GET /api/v1/admin/plugins",
        "value": "/api/v1/admin/plugins",
    } in response.json()
    assert {
        "label": "GET /api/v1/admin/routes",
        "value": "/api/v1/admin/routes",
    } in response.json()


def test_admin_lists_runtime_settings_without_secrets() -> None:
    """The admin plugin lists runtime settings without secret values."""

    settings = Settings(
        port=9001,
        service_name="aperture-test",
        log_level="debug",
        cache_backend="redis",
        cache_default_ttl_seconds=120,
        redis_url=RedisDsn("redis://:secret@redis.internal:6379/0"),
        auth_mode="api_key",
        api_keys={"admin-test": "secret"},
        api_key_header="X-Aperture-Key",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/admin/settings",
            headers={"X-Aperture-Key": "secret"},
        )

    assert response.status_code == 200
    assert response.json() == [
        {"label": "listen_addr", "value": "127.0.0.1"},
        {"label": "port", "value": "9001"},
        {"label": "service_name", "value": "aperture-test"},
        {"label": "log_level", "value": "debug"},
        {"label": "cache_backend", "value": "redis"},
        {"label": "cache_default_ttl_seconds", "value": "120"},
        {"label": "auth_mode", "value": "api_key"},
        {"label": "api_key_header", "value": "X-Aperture-Key"},
    ]
    assert "redis_url" not in response.text
    assert "secret" not in response.text
    assert "redis.internal" not in response.text
