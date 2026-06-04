"""Models for API authentication."""

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedService(BaseModel):
    """Service resolved from a valid API key."""

    service_name: str = Field(
        description="Service name linked to the API key.",
    )

    model_config = ConfigDict(extra="forbid")
