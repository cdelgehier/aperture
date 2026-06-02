"""Tests for application settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from aperture.settings import PluginConfig, Settings, load_settings


def test_default_settings() -> None:
    """Default settings are safe for local use."""

    settings = load_settings()

    assert str(settings.listen_addr) == "127.0.0.1"
    assert settings.port == 8000
    assert settings.auth_mode == "off"
    assert settings.cache_backend == "memory"


def test_admin_plugin_is_enabled_by_default() -> None:
    """The admin plugin is configured by default."""

    settings = load_settings()

    assert settings.plugins["admin"].enabled is True
    assert settings.plugins["admin"].module == "aperture.plugins.admin.main"
    assert settings.plugins["admin"].prefix == "/admin"


@pytest.mark.parametrize(
    ("raw_prefix", "expected_prefix"),
    [
        ("", ""),
        ("admin", "/admin"),
        ("admin/", "/admin"),
        ("/admin", "/admin"),
        ("/admin/", "/admin"),
    ],
)
def test_plugin_prefix_is_normalized(
    raw_prefix: str,
    expected_prefix: str,
) -> None:
    """Plugin prefixes are normalized for route mounting."""

    plugin = PluginConfig(prefix=raw_prefix)

    assert plugin.prefix == expected_prefix


def test_yaml_settings_are_loaded(tmp_path: Path) -> None:
    """Settings can be loaded from a YAML file."""

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        "port: 9000\n"
        "plugins:\n"
        "  admin:\n"
        "    enabled: true\n"
        "    module: aperture.plugins.admin.main\n"
        "    prefix: admin\n",
        encoding="utf-8",
    )

    settings = load_settings(settings_file)

    assert settings.port == 9000
    assert settings.plugins["admin"].prefix == "/admin"


def test_plugin_config_rejects_unknown_fields(tmp_path: Path) -> None:
    """Plugin config rejects typo fields."""

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        "plugins:\n"
        "  admin:\n"
        "    enabeld: false\n"
        "    module: aperture.plugins.admin.main\n"
        "    prefix: admin\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="enabeld"):
        load_settings(settings_file)


def test_environment_overrides_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment values override YAML values."""

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text("port: 9000\n", encoding="utf-8")
    monkeypatch.setenv("APT_PORT", "9100")

    settings = load_settings(settings_file)

    assert settings.port == 9100


def test_cache_ttl_must_be_positive() -> None:
    """Cache TTL must be greater than zero."""

    with pytest.raises(ValidationError):
        Settings(cache_default_ttl_seconds=0)
