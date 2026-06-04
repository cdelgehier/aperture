"""Tests for Problem Details responses."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from aperture.errors import ProblemDetails
from aperture.main import create_app


def test_problem_details_model_accepts_request_id() -> None:
    """Problem Details include the Aperture request id."""

    problem = ProblemDetails(
        title="Unauthorized",
        status=401,
        detail="Missing API key.",
        request_id="request-1",
    )

    assert problem.type == "about:blank"
    assert problem.request_id == "request-1"


def test_problem_details_model_rejects_unknown_fields() -> None:
    """Problem Details rejects typo fields."""

    adapter = TypeAdapter(ProblemDetails)

    with pytest.raises(ValidationError, match="reqest_id"):
        adapter.validate_python(
            {
                "title": "Error",
                "status": 500,
                "detail": "Failed.",
                "reqest_id": "request-1",
            }
        )


def test_http_exception_returns_problem_details() -> None:
    """HTTP errors use the Problem Details shape."""

    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        """Raise an HTTP error for the test."""

        raise HTTPException(status_code=418, detail="Teapot")

    with TestClient(app) as client:
        response = client.get("/boom", headers={"X-Request-ID": "request-1"})

    assert response.status_code == 418
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "I'm a Teapot",
        "status": 418,
        "detail": "Teapot",
        "request_id": "request-1",
    }


def test_http_exception_with_unknown_status_uses_generic_title() -> None:
    """Unknown HTTP status codes use a generic title."""

    app = create_app()

    @app.get("/unknown-status")
    async def unknown_status() -> None:
        """Raise an HTTP error with a non-standard status code."""

        raise HTTPException(status_code=599, detail="Network timeout")

    with TestClient(app) as client:
        response = client.get("/unknown-status")

    assert response.status_code == 599
    assert response.json()["title"] == "HTTP Error"


def test_unknown_route_returns_problem_details() -> None:
    """Missing routes use the Problem Details shape."""

    with TestClient(create_app()) as client:
        response = client.get("/yolo", headers={"X-Request-ID": "request-404"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Not Found",
        "request_id": "request-404",
    }
