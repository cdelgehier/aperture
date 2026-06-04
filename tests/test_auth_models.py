"""Tests for authentication models."""

import pytest
from pydantic import TypeAdapter, ValidationError

from aperture.models.auth import AuthenticatedService


def test_authenticated_service_model_accepts_service_name() -> None:
    """Authenticated service stores the resolved service name."""

    service = AuthenticatedService(service_name="internal-tool")

    assert service.service_name == "internal-tool"


def test_authenticated_service_model_rejects_unknown_fields() -> None:
    """Authenticated service rejects typo fields."""

    adapter = TypeAdapter(AuthenticatedService)

    with pytest.raises(ValidationError, match="extra"):
        adapter.validate_python(
            {
                "service_name": "internal-tool",
                "extra": "not allowed",
            }
        )
