"""Tests for Kubernetes health probes."""

import pytest
from fastapi.testclient import TestClient

from aperture.main import create_app
from aperture.models.plugin_config import PluginConfig
from aperture.settings import Settings


@pytest.mark.parametrize(
    ("path", "expected_body"),
    [
        ("/livez", {"status": "ok"}),
        ("/readyz", {"status": "ready", "plugins": ["admin"]}),
    ],
)
def test_health_probe_returns_expected_body(
    client: TestClient,
    path: str,
    expected_body: dict[str, object],
) -> None:
    """Health probes return their expected body."""

    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == expected_body


def test_readyz_returns_not_ready_when_plugin_fails() -> None:
    """The readiness probe fails when a plugin cannot load."""

    settings = Settings(
        plugins={
            "missing": PluginConfig(
                module="aperture.plugins.missing.main",
                prefix="/missing",
            )
        }
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["plugin_errors"][0]["name"] == "missing"
