"""Problem Details helpers for HTTP errors."""

from http import HTTPStatus

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException


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


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Convert FastAPI HTTP errors to Problem Details."""

    status_code = 500
    detail = "Internal Server Error"
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        detail = str(exc.detail)

    # Prefer the id set by our middleware, but keep a fallback for direct calls.
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = request.headers.get("X-Request-ID", "unknown")
    problem = ProblemDetails(
        title=_status_title(status_code),
        status=status_code,
        detail=detail,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


def _status_title(status_code: int) -> str:
    """Return the standard HTTP title for one status code."""

    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP Error"
