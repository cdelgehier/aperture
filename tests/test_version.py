"""Tests for package version data."""

import tomllib
from pathlib import Path

from aperture.version import __version__


def test_version_matches_project_metadata() -> None:
    """The package version follows pyproject metadata."""

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == pyproject["project"]["version"]
