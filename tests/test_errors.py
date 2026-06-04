"""Tests for Problem Details responses."""

import json

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from aperture.errors import http_exception_handler
from aperture.main import create_app
from aperture.models.problem_details import ProblemDetails


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


async def test_problem_details_falls_back_to_request_header_without_middleware() -> (
    None
):
    """Problem Details can still use request id without Aperture middleware."""

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/no-state",
        "headers": [(b"x-request-id", b"header-only")],
    }
    request = Request(scope)
    exception = StarletteHTTPException(status_code=400, detail="Bad request")

    response = await http_exception_handler(request, exception)

    body = json.loads(bytes(response.body))
    assert response.status_code == 400
    assert body["request_id"] == "header-only"
