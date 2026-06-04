"""Tests for the plugin loader."""

import sys
from types import ModuleType

from fastapi import APIRouter

from aperture.cache.store import MemoryCacheStore
from aperture.models.plugin_config import PluginConfig
from aperture.plugins.loader import PluginContext, load_plugins


def test_load_plugins_loads_enabled_plugin() -> None:
    """The loader imports an enabled plugin module."""

    plugin_module = ModuleType("tests.stub_plugin")
    cache = MemoryCacheStore()

    def create_router(context: PluginContext) -> APIRouter:
        """Stub router factory used by this test."""

        assert context.settings == {"key": "value"}
        assert context.prefix == "/stub"
        assert context.cache is cache
        return APIRouter()

    # Stub: the module gives the loader the router factory it expects.
    setattr(plugin_module, "create_router", create_router)  # noqa: B010
    sys.modules["tests.stub_plugin"] = plugin_module

    try:
        loaded, errors = load_plugins(
            {
                "stub": PluginConfig(
                    module="tests.stub_plugin",
                    prefix="/stub",
                    config={"key": "value"},
                )
            },
            cache=cache,
        )
    finally:
        sys.modules.pop("tests.stub_plugin", None)

    assert errors == []
    assert len(loaded) == 1
    assert loaded[0].name == "stub"
    assert loaded[0].prefix == "/stub"


def test_load_plugins_skips_disabled_plugin() -> None:
    """The loader skips disabled plugin entries."""

    loaded, errors = load_plugins(
        {
            "disabled": PluginConfig(
                enabled=False,
                module="aperture.plugins.missing.main",
            )
        }
    )

    assert loaded == []
    assert errors == []


def test_load_plugins_reports_import_error() -> None:
    """The loader returns an error when a plugin module is missing."""

    loaded, errors = load_plugins(
        {
            "missing": PluginConfig(
                module="aperture.plugins.missing.main",
            )
        }
    )

    assert loaded == []
    assert len(errors) == 1
    assert errors[0].name == "missing"
    assert errors[0].module == "aperture.plugins.missing.main"


def test_load_plugins_reports_bad_router_factory() -> None:
    """The loader returns an error when a plugin gives a bad router."""

    plugin_module = ModuleType("tests.bad_plugin")

    def create_router(context: PluginContext) -> object:
        """Stub router factory with a bad return value."""

        return {"prefix": context.prefix}

    setattr(plugin_module, "create_router", create_router)  # noqa: B010
    sys.modules["tests.bad_plugin"] = plugin_module

    try:
        loaded, errors = load_plugins({"bad": PluginConfig(module="tests.bad_plugin")})
    finally:
        sys.modules.pop("tests.bad_plugin", None)

    assert loaded == []
    assert len(errors) == 1
    assert errors[0].name == "bad"
    assert errors[0].error == "create_router must return APIRouter"
