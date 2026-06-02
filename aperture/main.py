"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException

from aperture.logger import configure_logging, get_logger
from aperture.models.select_item import SelectItem
from aperture.plugins.loader import load_plugins
from aperture.settings import Settings
from aperture.version import __version__


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""

    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)
    log = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Store app state when the service starts."""

        app.state.settings = resolved_settings
        plugins, plugin_errors = load_plugins(resolved_settings.plugins)
        app.state.plugins = plugins
        app.state.plugin_errors = plugin_errors
        for plugin in plugins:
            app.include_router(plugin.router, prefix=f"/api/v1{plugin.prefix}")
        log.info("aperture started", plugins=[plugin.name for plugin in plugins])
        yield
        log.info("aperture stopped")

    app = FastAPI(
        title="Aperture",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/", response_model=list[SelectItem])
    async def root() -> list[SelectItem]:
        """Return basic service information as select items."""

        return [SelectItem(label="Aperture", value=__version__)]

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        """Return a simple liveness answer for Kubernetes."""

        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, object]:
        """Return readiness and plugin load state for Kubernetes."""

        plugin_errors = getattr(app.state, "plugin_errors", [])
        if plugin_errors:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "plugin_errors": [
                        {
                            "name": error.name,
                            "module": error.module,
                            "error": error.error,
                        }
                        for error in plugin_errors
                    ],
                },
            )
        plugins = getattr(app.state, "plugins", [])
        return {"status": "ready", "plugins": [plugin.name for plugin in plugins]}

    return app


app = create_app()


def main() -> None:
    """Run the API server with settings from the environment."""

    settings = Settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "aperture.main:app",
        host=str(settings.listen_addr),
        port=settings.port,
        log_level=settings.log_level,
    )
