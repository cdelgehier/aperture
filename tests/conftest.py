"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aperture.main import create_app
from aperture.settings import Settings


@pytest.fixture
def settings() -> Settings:
    """Return default settings for tests."""

    return Settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Return a test client for the FastAPI app."""

    # Keep function scope so each test gets a fresh app state.
    with TestClient(create_app(settings)) as test_client:
        yield test_client
