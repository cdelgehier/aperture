"""Demo plugin that lists Paris drinking fountains."""

import asyncio
import json
from collections.abc import Mapping
from typing import Annotated, Any, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Query
from fastapi import Request as FastAPIRequest

from aperture.cache.store import (
    build_cache_key,
    get_or_set_cache,
    should_bypass_cache,
)
from aperture.logger import get_logger
from aperture.models.select_item import SelectItem
from aperture.plugins.loader import PluginContext


def create_router(context: PluginContext) -> APIRouter:
    """Create routes for the drinking fountains demo plugin."""

    # The router groups all routes exposed by this plugin.
    router = APIRouter(tags=["drinking-fountains"])
    log = get_logger(__name__)



    @router.get("/models", response_model=list[SelectItem])
    async def list_fountain_models(request: FastAPIRequest) -> list[SelectItem]:
        """Return fountain models as select items."""

        ttl_seconds = int(context.settings.get("ttl_seconds", 300))

        # Models do not depend on user filters, so the cache key has no params.
        cache_key = build_cache_key(
            plugin="demo_data_gouv",
            resource="models",
            params={},
        )

        async def fetch_live() -> list[dict[str, Any]]:
            """Fetch live model items when cache cannot be used."""

            return await _fetch_live_model_items()

        cached_items = await get_or_set_cache(
            context.cache,
            cache_key,
            ttl=ttl_seconds,
            # nocache=true skips the read but still refreshes Redis after fetch.
            nocache=should_bypass_cache(request.query_params.get("nocache")),
            logger=log,
            fetch_live=fetch_live,
        )
        return [SelectItem.model_validate(item) for item in cached_items]



    @router.get("/fountains", response_model=list[SelectItem])
    async def list_drinking_fountains(
        request: FastAPIRequest,
        model: Annotated[str | None, Query()] = None,
        communes: Annotated[list[str] | None, Query(alias="commune")] = None,
    ) -> list[SelectItem]:
        """Return available fountains as select items."""

        page_size = int(context.settings.get("page_size", 5))
        ttl_seconds = int(context.settings.get("ttl_seconds", 300))

        # Sort repeated communes so URL order does not change the cache key.
        selected_communes = sorted(communes or [])

        # Every filter that changes the response must be part of the cache key.
        cache_key = build_cache_key(
            plugin="demo_data_gouv",
            resource="fountains",
            params={
                "page_size": page_size,
                "model": model,
                "communes": selected_communes,
            },
        )
        cache = context.cache

        async def fetch_live() -> list[dict[str, Any]]:
            """Fetch live items when cache cannot be used."""

            return await _fetch_live_fountain_items(
                page_size,
                model,
                selected_communes,
            )

        cached_items = await get_or_set_cache(
            cache,
            cache_key,
            ttl=ttl_seconds,
            # nocache=true forces a live Paris Data lookup.
            nocache=should_bypass_cache(request.query_params.get("nocache")),
            logger=log,
            fetch_live=fetch_live,
        )
        return [SelectItem.model_validate(item) for item in cached_items]

    @router.get("/communes", response_model=list[SelectItem])
    async def list_fountain_communes(request: FastAPIRequest) -> list[SelectItem]:
        """Return fountain communes as select items."""

        ttl_seconds = int(context.settings.get("ttl_seconds", 300))

        # Communes do not depend on user filters, so the cache key has no params.
        cache_key = build_cache_key(
            plugin="demo_data_gouv",
            resource="communes",
            params={},
        )

        async def fetch_live() -> list[dict[str, Any]]:
            """Fetch live commune items when cache cannot be used."""

            return await _fetch_live_commune_items()

        cached_items = await get_or_set_cache(
            context.cache,
            cache_key,
            ttl=ttl_seconds,
            # nocache=true skips the read but still refreshes Redis after fetch.
            nocache=should_bypass_cache(request.query_params.get("nocache")),
            logger=log,
            fetch_live=fetch_live,
        )
        return [SelectItem.model_validate(item) for item in cached_items]

    return router


async def _fetch_live_model_items() -> list[dict[str, Any]]:
    """Fetch live fountain models and return select item dictionaries."""

    # Blocking HTTP is moved to a worker thread so the async route stays free.
    payload = await asyncio.to_thread(_fetch_models)
    records = payload.get("results", [])
    if not isinstance(records, list):
        records = []

    items: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        record_data = cast(Mapping[str, Any], record)
        model = record_data.get("modele")
        if not isinstance(model, str) or not model:
            continue
        # SelectItem is the public Aperture shape: label and value.
        items.append(SelectItem(label=model, value=model).model_dump())
    return items


async def _fetch_live_fountain_items(
    page_size: int,
    model: str | None,
    communes: list[str],
) -> list[dict[str, Any]]:
    """Fetch live fountains and return select item dictionaries."""

    # Paris Data does the filtering. The plugin only maps results to SelectItem.
    payload = await asyncio.to_thread(
        _fetch_fountains,
        page_size=page_size,
        model=model,
        communes=communes,
    )
    fountains = payload.get("results", [])
    if not isinstance(fountains, list):
        fountains = []

    items: list[dict[str, str]] = []
    for fountain in fountains:
        # A select value needs coordinates, so skip records that miss them.
        if not isinstance(fountain, dict) or not _has_coordinates(fountain):
            continue
        fountain_data = cast(Mapping[str, Any], fountain)
        items.append(
            SelectItem(
                label=_build_label(fountain_data),
                value=_build_value(fountain_data),
            ).model_dump()
        )
    return items


async def _fetch_live_commune_items() -> list[dict[str, Any]]:
    """Fetch live communes and return select item dictionaries."""

    # Blocking HTTP is moved to a worker thread so the async route stays free.
    payload = await asyncio.to_thread(_fetch_communes)
    records = payload.get("results", [])
    if not isinstance(records, list):
        records = []

    items: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        record_data = cast(Mapping[str, Any], record)
        commune = record_data.get("commune")
        if not isinstance(commune, str) or not commune:
            continue
        items.append(SelectItem(label=commune, value=commune).model_dump())
    return items


def _fetch_models() -> dict[str, object]:
    """Fetch available drinking fountain models from Paris open data."""

    # group_by returns one row per model instead of every fountain.
    params = urlencode(
        {
            "select": "modele",
            "where": "dispo='OUI'",
            "group_by": "modele",
            "order_by": "modele",
            "limit": 100,
        }
    )
    request = Request(
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
        f"fontaines-a-boire/records?{params}",
        headers={"User-Agent": "aperture-demo/0.1"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_fountains(
    page_size: int,
    model: str | None,
    communes: list[str],
) -> dict[str, object]:
    """Fetch drinking fountains from Paris open data."""

    where = _build_where_clause(model=model, communes=communes)

    # where filters the remote dataset before we map records to SelectItem.
    params = urlencode(
        {
            "limit": page_size,
            "where": where,
            "order_by": "modele",
        }
    )
    request = Request(
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
        f"fontaines-a-boire/records?{params}",
        headers={"User-Agent": "aperture-demo/0.1"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_communes() -> dict[str, object]:
    """Fetch available fountain communes from Paris open data."""

    # group_by returns one row per commune instead of every fountain.
    params = urlencode(
        {
            "select": "commune",
            "where": "dispo='OUI'",
            "group_by": "commune",
            "order_by": "commune",
            "limit": 100,
        }
    )
    request = Request(
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
        f"fontaines-a-boire/records?{params}",
        headers={"User-Agent": "aperture-demo/0.1"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_where_clause(*, model: str | None, communes: list[str]) -> str:
    """Build the Paris Data filter used for fountains."""

    # Start with available fountains only.
    filters = ["dispo='OUI'"]
    if model:
        filters.append(f"modele={_quote_where_value(model)}")
    if communes:
        # Repeated commune params mean OR: commune A or commune B.
        commune_filters = [
            f"commune={_quote_where_value(commune)}" for commune in communes
        ]
        filters.append(f"({' OR '.join(commune_filters)})")
    return " AND ".join(filters)


def _quote_where_value(value: str) -> str:
    """Quote one value for a Paris Data where clause."""

    # Paris Data strings use single quotes. Escape user quotes by doubling them.
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _has_coordinates(fountain: object) -> bool:
    """Return true when a fountain has lon and lat."""

    if not isinstance(fountain, dict):
        return False
    fountain_data = cast(Mapping[str, Any], fountain)
    geo_point = fountain_data.get("geo_point_2d")
    return isinstance(geo_point, dict) and "lon" in geo_point and "lat" in geo_point


def _build_label(fountain: Mapping[str, Any]) -> str:
    """Build a readable fountain name for the select label."""

    # The dataset has no real name field, so build one from useful columns.
    modele = fountain.get("modele") or fountain.get("type_objet") or "Fontaine"
    voie = fountain.get("voie") or "adresse inconnue"
    commune = fountain.get("commune") or "commune inconnue"
    return f"{modele} - {voie} - {commune}"


def _build_value(fountain: Mapping[str, Any]) -> str:
    """Use coordinates as the select value."""

    # The widget receives a stable "lat,lon" value.
    geo_point = fountain["geo_point_2d"]
    return f"{geo_point['lat']},{geo_point['lon']}"
