"""Tests for logging setup."""

from unittest.mock import patch

import structlog

from aperture.logger import configure_logging, get_logger


def test_configure_logging_uses_json_renderer_when_stderr_is_not_tty() -> None:
    """Non-TTY logging uses JSON for containers."""

    with (
        patch("aperture.logger.sys.stderr.isatty", return_value=False),
        patch("aperture.logger.structlog.configure") as configure,
    ):
        configure_logging("debug")

    processors = configure.call_args.kwargs["processors"]

    assert any(
        isinstance(processor, structlog.processors.JSONRenderer)
        for processor in processors
    )


def test_configure_logging_uses_console_renderer_when_stderr_is_tty() -> None:
    """TTY logging uses a console renderer for local runs."""

    with (
        patch("aperture.logger.sys.stderr.isatty", return_value=True),
        patch("aperture.logger.structlog.configure") as configure,
    ):
        configure_logging("info")

    processors = configure.call_args.kwargs["processors"]

    assert any(
        isinstance(processor, structlog.dev.ConsoleRenderer) for processor in processors
    )


def test_get_logger_returns_bound_logger() -> None:
    """Logger lookup returns a structlog logger."""

    logger = get_logger("aperture.test")

    assert logger is not None
