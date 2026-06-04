"""Tests for request middleware."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from aperture.main import create_app


def test_request_id_header_is_reused() -> None:
    """Incoming request id is returned to the caller."""

    with TestClient(create_app()) as client:
        response = client.get("/", headers={"X-Request-ID": "request-1"})

    assert response.headers["X-Request-ID"] == "request-1"


def test_request_id_header_is_generated() -> None:
    """Missing request id is generated."""

    with (
        patch("aperture.middlewares.request_context.uuid4", return_value="generated-1"),
        TestClient(create_app()) as client,
    ):
        response = client.get("/")

    assert response.headers["X-Request-ID"] == "generated-1"


def test_security_header_is_added() -> None:
    """The middleware adds a basic content sniffing header."""

    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_request_logging_records_request_data() -> None:
    """HTTP middleware logs request data."""

    with (
        patch("aperture.middlewares.request_context.get_logger") as get_logger,
        TestClient(create_app()) as client,
    ):
        logger = get_logger.return_value
        response = client.get("/", headers={"X-Request-ID": "request-1"})

    assert response.status_code == 200
    logger.info.assert_called_with(
        "http request finished",
        request_id="request-1",
        method="GET",
        path="/",
        status=200,
        duration_ms=logger.info.call_args.kwargs["duration_ms"],
    )


def test_request_id_is_used_by_problem_details() -> None:
    """Generated request id is used by Problem Details."""

    with (
        patch("aperture.middlewares.request_context.uuid4", return_value="generated-1"),
        TestClient(create_app()) as client,
    ):
        response = client.get("/missing")

    assert response.headers["X-Request-ID"] == "generated-1"
    assert response.json()["request_id"] == "generated-1"
