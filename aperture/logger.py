"""Logging setup for Aperture."""

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "info", service_name: str = "aperture") -> None:
    """Configure structlog for local use and containers."""

    # Keep Python logging and structlog on the same minimum level.
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)

    # Service name is bound once here, then request data is added per request.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service_name=service_name)

    # Processors enrich each log line before it is rendered.
    processors: list[Any] = [
        # Add values stored with structlog.contextvars.bind_contextvars().
        structlog.contextvars.merge_contextvars,
        # Add the log level as a field.
        structlog.processors.add_log_level,
        # Use UTC timestamps so logs are stable across environments.
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Keep stack and exception data readable when they exist.
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if sys.stderr.isatty():
        # Local terminals should be easy to read.
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # Containers should emit JSON for log collectors.
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        # Drop debug logs when the configured level is higher.
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        # Write to stderr, which is the normal stream for app logs.
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Return a structlog logger for one module."""

    return structlog.get_logger(name)
