"""Models for RFC 7807 error responses."""

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetails(BaseModel):
    """RFC 7807 error response with Aperture request id."""

    type: str = Field(
        default="about:blank",
        description="Problem type URI.",
    )
    title: str = Field(
        description="Short error title.",
    )
    status: int = Field(
        description="HTTP status code.",
    )
    detail: str = Field(
        description="Human readable error detail.",
    )
    request_id: str = Field(
        description="Request id used to find logs.",
    )

    model_config = ConfigDict(extra="forbid")
