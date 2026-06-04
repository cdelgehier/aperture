"""Async cache stores used by Aperture."""

import hashlib
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from redis.asyncio import Redis

if TYPE_CHECKING:
    from aperture.settings import Settings


class CacheStore(Protocol):
    """Small async cache contract used by plugins."""

    async def get(self, key: str) -> Any | None:
        """Return one cached value, or None when missing."""
        ...

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Store one JSON value for a number of seconds."""
        ...

    async def delete(self, key: str) -> None:
        """Delete one cached value."""
        ...

    async def delete_namespace(self, namespace: str) -> None:
        """Delete all keys that start with a namespace."""
        ...

    async def close(self) -> None:
        """Close cache resources."""
        ...


class CacheLogger(Protocol):
    """Logger shape used by safe cache helpers."""

    def debug(self, event: str, **values: object) -> Any:
        """Log one cache debug event."""
        ...

    def warning(self, event: str, **values: object) -> Any:
        """Log one cache warning."""
        ...


class RedisClient(Protocol):
    """Small Redis client shape used by RedisCacheStore."""

    def get(self, key: str, /) -> Awaitable[str | bytes | None]:
        """Return one Redis value."""
        ...

    def set(self, key: str, value: str, /, ex: int) -> Awaitable[Any]:
        """Set one Redis value with an expiry."""
        ...

    def delete(self, *keys: str | bytes) -> Awaitable[Any]:
        """Delete one or more Redis keys."""
        ...

    def scan_iter(self, match: str) -> AsyncIterator[str | bytes]:
        """Yield Redis keys that match a pattern."""
        ...

    def aclose(self) -> Awaitable[Any]:
        """Close the Redis client."""
        ...


@dataclass(frozen=True)
class MemoryCacheEntry:
    """One memory cache item with its expiry time."""

    value: Any
    expires_at: float


class MemoryCacheStore:
    """In-process cache store for local use and tests."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        """Create an empty memory cache."""

        self._clock = clock or time.monotonic
        self._items: dict[str, MemoryCacheEntry] = {}
        self.closed = False

    async def get(self, key: str) -> Any | None:
        """Return a cached value when it exists and is still fresh."""

        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._items.pop(key, None)
            return None
        return _json_copy(entry.value)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Store a JSON-compatible value in memory."""

        self._items[key] = MemoryCacheEntry(
            value=_json_copy(value),
            expires_at=self._clock() + ttl,
        )

    async def delete(self, key: str) -> None:
        """Delete one memory cache value."""

        self._items.pop(key, None)

    async def delete_namespace(self, namespace: str) -> None:
        """Delete memory cache values that start with a namespace."""

        prefix = _namespace_prefix(namespace)
        for key in list(self._items):
            if key.startswith(prefix):
                self._items.pop(key, None)

    async def close(self) -> None:
        """Close the memory cache store."""

        self.closed = True


class RedisCacheStore:
    """Redis cache store using JSON strings."""

    def __init__(self, redis: RedisClient) -> None:
        """Keep the Redis client used by this store."""

        self._redis = redis

    async def get(self, key: str) -> Any | None:
        """Return a decoded cached value from Redis."""

        cached = await self._redis.get(key)
        if cached is None:
            return None
        if isinstance(cached, bytes):
            cached = cached.decode()
        return json.loads(cached)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Store a JSON-compatible value in Redis."""

        await self._redis.set(key, json.dumps(value, sort_keys=True), ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete one Redis cache value."""

        await self._redis.delete(key)

    async def delete_namespace(self, namespace: str) -> None:
        """Delete Redis keys that start with a namespace."""

        keys = [key async for key in self._redis.scan_iter(match=f"{namespace}:*")]
        if keys:
            await self._redis.delete(*keys)

    async def close(self) -> None:
        """Close the Redis client."""

        await self._redis.aclose()


def build_cache_key(
    *,
    plugin: str,
    resource: str,
    scope: tuple[str, ...] = (),
    params: dict[str, Any],
) -> str:
    """Build a stable cache key for one plugin resource request."""

    encoded_params = json.dumps(params, sort_keys=True, separators=(",", ":"))
    params_hash = hashlib.sha256(encoded_params.encode()).hexdigest()
    scope_part = ":".join(scope)
    key_parts = ["plugin", plugin, "resource", resource]
    if scope_part:
        key_parts.extend(["scope", scope_part])
    key_parts.extend(["params", params_hash])
    return ":".join(key_parts)


def should_bypass_cache(raw_value: str | None) -> bool:
    """Return true when the nocache query value asks to skip cache."""

    if raw_value is None:
        return False
    return raw_value.lower() in {"1", "true", "yes", "on"}


def create_cache_store(settings: Settings) -> CacheStore:
    """Create the configured cache store."""

    if settings.cache_backend == "memory":
        return MemoryCacheStore()
    return RedisCacheStore(Redis.from_url(str(settings.redis_url)))


async def safe_get_cache(
    cache: CacheStore,
    key: str,
    *,
    logger: CacheLogger,
) -> Any | None:
    """Read cache and return None if the backend fails."""

    try:
        value = await cache.get(key)
        if value is None:
            logger.debug("cache miss", key=key)
            return None
        logger.debug("cache hit", key=key)
        return value
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache get failed", key=key, error=str(exc))
        return None


async def safe_set_cache(
    cache: CacheStore,
    key: str,
    value: Any,
    *,
    ttl: int,
    logger: CacheLogger,
) -> None:
    """Write cache and continue if the backend fails."""

    try:
        await cache.set(key, value, ttl)
        logger.debug("cache set", key=key, ttl=ttl)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache set failed", key=key, error=str(exc))


async def get_or_set_cache(
    cache: CacheStore | None,
    key: str,
    *,
    ttl: int,
    nocache: bool,
    logger: CacheLogger,
    fetch_live: Callable[[], Awaitable[Any]],
) -> Any:
    """Return cached data or fetch live data and refresh the cache."""

    if cache is None:
        logger.debug("cache disabled", key=key)
        return await fetch_live()

    if nocache:
        logger.debug("cache bypass", key=key)
    else:
        cached_value = await safe_get_cache(cache, key, logger=logger)
        if cached_value is not None:
            return cached_value

    live_value = await fetch_live()
    await safe_set_cache(cache, key, live_value, ttl=ttl, logger=logger)
    return live_value


async def safe_delete_cache(
    cache: CacheStore,
    key: str,
    *,
    logger: CacheLogger,
) -> None:
    """Delete one cache item and continue if the backend fails."""

    try:
        await cache.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache delete failed", key=key, error=str(exc))


async def safe_delete_cache_namespace(
    cache: CacheStore,
    namespace: str,
    *,
    logger: CacheLogger,
) -> None:
    """Delete a cache namespace and continue if the backend fails."""

    try:
        await cache.delete_namespace(namespace)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "cache namespace delete failed",
            namespace=namespace,
            error=str(exc),
        )


def _json_copy(value: Any) -> Any:
    """Validate JSON support and return a detached value copy."""

    return json.loads(json.dumps(value, sort_keys=True))


def _namespace_prefix(namespace: str) -> str:
    """Make namespace deletion match full key parts."""

    return f"{namespace}:"
