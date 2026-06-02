"""Tests for the root endpoint."""

from fastapi.testclient import TestClient

from aperture.version import __version__


def test_root_returns_select_item_contract(client: TestClient) -> None:
    """The root endpoint returns a list of select items."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == [{"label": "Aperture", "value": __version__}]
