"""Load plugins from Python modules.

A plugin is a small Python module that gives Aperture a FastAPI router.
The module must expose a function named ``create_router``.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from fastapi import APIRouter

from aperture.cache.store import CacheStore
from aperture.models.plugin_config import PluginConfig


@dataclass(frozen=True)
class PluginContext:
    """Data given to a plugin when its router is created."""

    #: Free settings for this plugin from ``Settings.plugins``.
    settings: dict[str, Any]
    #: URL prefix used when the plugin is mounted in the API.
    prefix: str
    #: Shared cache store available to plugins.
    cache: CacheStore | None = None


@dataclass(frozen=True)
class LoadedPlugin:
    """A plugin that is ready to be mounted in FastAPI."""

    #: Logical plugin name, like ``admin``.
    name: str
    #: URL prefix, like ``/admin``.
    prefix: str
    #: FastAPI router returned by the plugin.
    router: APIRouter


@dataclass(frozen=True)
class PluginLoadError:
    """A plugin load failure kept for readiness checks."""

    #: Logical plugin name from settings.
    name: str
    #: Python module path that failed to load.
    module: str
    #: Short error message for operators.
    error: str


def load_plugins(
    plugin_configs: dict[str, PluginConfig],
    cache: CacheStore | None = None,
) -> tuple[list[LoadedPlugin], list[PluginLoadError]]:
    """Load enabled plugins and keep failures as data.

    The app should still start if one plugin fails to load. The readiness
    probe can then report the failure with a clear error.
    """

    loaded: list[LoadedPlugin] = []
    errors: list[PluginLoadError] = []

    for name, config in plugin_configs.items():
        if not config.enabled:
            continue

        # If no module is set, use the internal plugin path convention.
        module_name = config.module or f"aperture.plugins.{name}.main"
        try:
            # Import the plugin module, for example aperture.plugins.admin.main.
            module = import_module(module_name)

            # Every plugin module must expose create_router(context).
            create_router = module.create_router

            # Give the plugin only its own settings and mount prefix.
            context = PluginContext(
                settings=config.config,
                prefix=config.prefix,
                cache=cache,
            )

            # Ask the plugin to build its FastAPI router.
            router = create_router(context)

            # Keep the app safe if a plugin returns the wrong object.
            if not isinstance(router, APIRouter):
                msg = "create_router must return APIRouter"
                raise TypeError(msg)
        except Exception as exc:  # noqa: BLE001
            # Keep the failure as data. /readyz will expose it later.
            errors.append(
                PluginLoadError(name=name, module=module_name, error=str(exc))
            )
            continue

        # Only valid routers reach this list and get mounted by the app.
        loaded.append(LoadedPlugin(name=name, prefix=config.prefix, router=router))

    return loaded, errors
