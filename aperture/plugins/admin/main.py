"""Admin plugin with select-item introspection routes."""

from fastapi import APIRouter, Request

from aperture.models.select_item import SelectItem
from aperture.plugins.loader import PluginContext
from aperture.settings import Settings


def create_router(context: PluginContext) -> APIRouter:
    """Create the admin plugin router."""

    router = APIRouter(tags=["admin"])

    @router.get("/plugins", response_model=list[SelectItem])
    async def list_plugins(request: Request) -> list[SelectItem]:
        """List plugins loaded by the app."""

        plugins = getattr(request.app.state, "plugins", [])
        return [
            SelectItem(label=f"{plugin.name} - {plugin.prefix}", value=plugin.name)
            for plugin in plugins
        ]

    @router.get("/routes", response_model=list[SelectItem])
    async def list_routes(request: Request) -> list[SelectItem]:
        """List select API routes known by the app."""

        items: list[SelectItem] = []
        for route in request.app.routes:
            path = getattr(route, "path", "")
            methods = sorted(getattr(route, "methods", []) or [])
            if not path.startswith("/api/v1"):
                continue
            items.append(SelectItem(label=f"{','.join(methods)} {path}", value=path))
        return items

    @router.get("/settings", response_model=list[SelectItem])
    async def list_settings(request: Request) -> list[SelectItem]:
        """List safe runtime settings for operators."""

        settings: Settings = request.app.state.settings
        return [
            SelectItem(label="listen_addr", value=str(settings.listen_addr)),
            SelectItem(label="port", value=str(settings.port)),
            SelectItem(label="service_name", value=settings.service_name),
            SelectItem(label="log_level", value=settings.log_level),
            SelectItem(
                label="cache_backend",
                value=settings.cache_backend,
            ),
            SelectItem(
                label="cache_default_ttl_seconds",
                value=str(settings.cache_default_ttl_seconds),
            ),
            SelectItem(label="auth_mode", value=settings.auth_mode),
            SelectItem(label="api_key_header", value=settings.api_key_header),
        ]

    return router
