"""Tests for the FastAPI app factory and server entrypoint."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aperture.cache.store import MemoryCacheStore
from aperture.main import create_app, main
from aperture.settings import Settings


def test_create_app_returns_fastapi_app(settings: Settings) -> None:
    """The app factory returns a FastAPI app."""

    app = create_app(settings)

    assert isinstance(app, FastAPI)
    assert app.title == "Aperture"


def test_lifespan_binds_settings(settings: Settings) -> None:
    """The app lifespan stores settings in app state."""

    app = create_app(settings)

    with TestClient(app):
        assert app.state.settings is settings


def test_lifespan_binds_cache_store(settings: Settings) -> None:
    """The app lifespan stores the configured cache in app state."""

    app = create_app(settings)

    with TestClient(app):
        assert isinstance(app.state.cache, MemoryCacheStore)


def test_lifespan_closes_cache_store(settings: Settings) -> None:
    """The app lifespan closes the cache store on shutdown."""

    app = create_app(settings)

    with TestClient(app):
        cache = app.state.cache

    assert cache.closed is True


@pytest.mark.parametrize(
    ("listen_addr", "port", "log_level", "service_name"),
    [
        ("0.0.0.0", "9000", "debug", "aperture-dev"),
        ("127.0.0.1", "8100", "info", "aperture-local"),
    ],
)
def test_main_runs_uvicorn_with_settings(
    monkeypatch: pytest.MonkeyPatch,
    listen_addr: str,
    port: str,
    log_level: str,
    service_name: str,
) -> None:
    """The CLI entrypoint starts Uvicorn with configured values."""

    monkeypatch.setenv("APT_LISTEN_ADDR", listen_addr)
    monkeypatch.setenv("APT_PORT", port)
    monkeypatch.setenv("APT_LOG_LEVEL", log_level)
    monkeypatch.setenv("APT_SERVICE_NAME", service_name)

    with (
        patch("aperture.main.configure_logging") as configure_logging,
        patch("aperture.main.uvicorn.run") as run,
    ):
        main()

    configure_logging.assert_called_once_with(log_level, service_name)
    run.assert_called_once_with(
        "aperture.main:app",
        host=listen_addr,
        port=int(port),
        log_level=log_level,
    )
