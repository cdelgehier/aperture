"""Tests for package version data."""

from aperture.version import __version__


def test_version_matches_initial_project_version() -> None:
    """The package starts at version 0.1.0."""

    assert __version__ == "0.1.0"
