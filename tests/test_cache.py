"""Tests for cache stores and cache helpers."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest

from aperture.cache.store import (
    MemoryCacheStore,
    RedisCacheStore,
    build_cache_key,
    create_cache_store,
    safe_delete_cache,
    safe_delete_cache_namespace,
    safe_get_cache,
    safe_set_cache,
    should_bypass_cache,
)
from aperture.settings import Settings


class FakeRedisClient:
    """Fake Redis client with the small API used by RedisCacheStore."""

    def __init__(self) -> None:
        """Store Redis values in memory for tests."""

        self.values: dict[str, str | bytes] = {}
        self.ttls: dict[str, int] = {}
        self.deleted_patterns: list[str] = []
        self.closed = False

    async def get(self, key: str) -> str | bytes | None:
        """Return a cached value."""

        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        """Store a cached value with its TTL."""

        self.values[key] = value
        self.ttls[key] = ex

    async def delete(self, *keys: str | bytes) -> None:
        """Delete one or more keys."""

        for key in keys:
            if isinstance(key, bytes):
                key = key.decode()
            self.values.pop(key, None)
            self.ttls.pop(key, None)

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        """Yield keys that match a namespace prefix."""

        self.deleted_patterns.append(match)
        prefix = match.removesuffix("*")
        for key in self.values:
            if key.startswith(prefix):
                yield key

    async def aclose(self) -> None:
        """Close the fake Redis connection."""

        self.closed = True


class RaisingCacheStore:
    """Fake cache store that raises on every operation."""

    async def get(self, key: str) -> None:
        """Raise on cache read."""

        raise RuntimeError(f"get failed for {key}")

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Raise on cache write."""

        raise RuntimeError(f"set failed for {key}")

    async def delete(self, key: str) -> None:
        """Raise on cache delete."""

        raise RuntimeError(f"delete failed for {key}")

    async def delete_namespace(self, namespace: str) -> None:
        """Raise on namespace delete."""

        raise RuntimeError(f"delete namespace failed for {namespace}")

    async def close(self) -> None:
        """Raise on close."""

        raise RuntimeError("close failed")


class SpyLogger:
    """Spy logger that records warning calls."""

    def __init__(self) -> None:
        """Create an empty warning list."""

        self.warnings: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **values: object) -> None:
        """Record one warning call."""

        self.warnings.append((event, values))


def test_build_cache_key_is_stable_for_param_order() -> None:
    """Cache keys do not change when param order changes."""

    first = build_cache_key(
        plugin="aws",
        resource="vpcs",
        scope=("account", "123456789012", "region", "eu-west-1"),
        params={"name": "prod", "limit": 20},
    )
    second = build_cache_key(
        plugin="aws",
        resource="vpcs",
        scope=("account", "123456789012", "region", "eu-west-1"),
        params={"limit": 20, "name": "prod"},
    )

    assert first == second
    assert first.startswith(
        "plugin:aws:resource:vpcs:scope:account:123456789012:region:eu-west-1:params:"
    )
    assert not first.startswith("/accounts/")


def test_build_cache_key_supports_non_cloud_scope() -> None:
    """Cache keys support plugins that are not cloud resources."""

    key = build_cache_key(
        plugin="gitlab",
        resource="repositories",
        scope=("group", "platform"),
        params={"archived": False},
    )

    assert key.startswith("plugin:gitlab:resource:repositories:scope:group:platform:")
    assert ":account:" not in key
    assert ":region:" not in key


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, False),
        ("", False),
        ("false", False),
        ("0", False),
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
    ],
)
def test_should_bypass_cache(raw_value: str | None, expected: bool) -> None:
    """The nocache query value controls cache bypass."""

    assert should_bypass_cache(raw_value) is expected


@pytest.mark.asyncio
async def test_memory_cache_get_set_delete() -> None:
    """Memory cache stores JSON-compatible values."""

    cache = MemoryCacheStore(clock=lambda: 100.0)
    value = {"items": [{"label": "prod", "value": "vpc-123"}]}

    await cache.set("key", value, ttl=30)

    assert await cache.get("key") == value

    await cache.delete("key")

    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_memory_cache_expires_values() -> None:
    """Memory cache drops values after their TTL."""

    now = 100.0
    cache = MemoryCacheStore(clock=lambda: now)

    await cache.set("key", {"value": "fresh"}, ttl=10)
    now = 111.0

    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_memory_cache_delete_namespace() -> None:
    """Memory cache deletes all keys that start with a namespace."""

    cache = MemoryCacheStore(clock=lambda: 100.0)
    await cache.set("account:region:aws:vpcs:1", {"value": 1}, ttl=30)
    await cache.set("account:region:aws:subnets:1", {"value": 2}, ttl=30)
    await cache.set("other:region:aws:vpcs:1", {"value": 3}, ttl=30)

    await cache.delete_namespace("account:region:aws")

    assert await cache.get("account:region:aws:vpcs:1") is None
    assert await cache.get("account:region:aws:subnets:1") is None
    assert await cache.get("other:region:aws:vpcs:1") == {"value": 3}


@pytest.mark.asyncio
async def test_memory_cache_rejects_non_json_values() -> None:
    """Memory cache rejects values that JSON cannot encode."""

    cache = MemoryCacheStore()

    with pytest.raises(TypeError):
        await cache.set("key", {"bad": object()}, ttl=30)


@pytest.mark.asyncio
async def test_redis_cache_uses_json_and_ttl() -> None:
    """Redis cache stores JSON strings with the requested TTL."""

    redis = FakeRedisClient()
    cache = RedisCacheStore(redis)
    value: dict[str, Any] = {"items": [{"label": "prod", "value": "vpc-123"}]}

    await cache.set("key", value, ttl=45)

    assert redis.ttls["key"] == 45
    assert await cache.get("key") == value


@pytest.mark.asyncio
async def test_redis_cache_decodes_byte_values() -> None:
    """Redis cache accepts byte values from Redis."""

    redis = FakeRedisClient()
    redis.values["key"] = b'{"value": "bytes"}'
    cache = RedisCacheStore(redis)

    assert await cache.get("key") == {"value": "bytes"}


@pytest.mark.asyncio
async def test_redis_cache_delete() -> None:
    """Redis cache deletes one key."""

    redis = FakeRedisClient()
    cache = RedisCacheStore(redis)
    await cache.set("key", {"value": "stored"}, ttl=30)

    await cache.delete("key")

    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_redis_cache_delete_namespace() -> None:
    """Redis cache deletes keys found by namespace scan."""

    redis = FakeRedisClient()
    cache = RedisCacheStore(redis)
    await cache.set("account:region:aws:vpcs:1", {"value": 1}, ttl=30)
    await cache.set("account:region:aws:subnets:1", {"value": 2}, ttl=30)
    await cache.set("other:region:aws:vpcs:1", {"value": 3}, ttl=30)

    await cache.delete_namespace("account:region:aws")

    assert await cache.get("account:region:aws:vpcs:1") is None
    assert await cache.get("account:region:aws:subnets:1") is None
    assert await cache.get("other:region:aws:vpcs:1") == {"value": 3}
    assert redis.deleted_patterns == ["account:region:aws:*"]


@pytest.mark.asyncio
async def test_redis_cache_close() -> None:
    """Redis cache closes its Redis client."""

    redis = FakeRedisClient()
    cache = RedisCacheStore(redis)

    await cache.close()

    assert redis.closed is True


@pytest.mark.asyncio
async def test_memory_cache_close_is_noop() -> None:
    """Memory cache close is safe."""

    cache = MemoryCacheStore()

    await cache.close()


def test_create_cache_store_uses_redis_backend() -> None:
    """The cache factory creates Redis stores for Redis settings."""

    redis = FakeRedisClient()
    settings = Settings(cache_backend="redis")

    with patch("aperture.cache.store.Redis.from_url", return_value=redis) as from_url:
        cache = create_cache_store(settings)

    assert isinstance(cache, RedisCacheStore)
    from_url.assert_called_once_with(str(settings.redis_url))


@pytest.mark.asyncio
async def test_safe_get_cache_falls_back_on_error() -> None:
    """Safe cache reads return None when cache backend fails."""

    logger = SpyLogger()

    value = await safe_get_cache(RaisingCacheStore(), "key", logger=logger)

    assert value is None
    assert logger.warnings[0][0] == "cache get failed"
    assert logger.warnings[0][1]["key"] == "key"


@pytest.mark.asyncio
async def test_safe_set_cache_logs_and_continues_on_error() -> None:
    """Safe cache writes log errors and continue."""

    logger = SpyLogger()

    await safe_set_cache(
        RaisingCacheStore(),
        "key",
        {"value": "stored"},
        ttl=30,
        logger=logger,
    )

    assert logger.warnings[0][0] == "cache set failed"
    assert logger.warnings[0][1]["key"] == "key"


@pytest.mark.asyncio
async def test_safe_delete_cache_logs_and_continues_on_error() -> None:
    """Safe cache deletes log errors and continue."""

    logger = SpyLogger()

    await safe_delete_cache(RaisingCacheStore(), "key", logger=logger)

    assert logger.warnings[0][0] == "cache delete failed"
    assert logger.warnings[0][1]["key"] == "key"


@pytest.mark.asyncio
async def test_safe_delete_cache_namespace_logs_and_continues_on_error() -> None:
    """Safe namespace deletes log errors and continue."""

    logger = SpyLogger()

    await safe_delete_cache_namespace(
        RaisingCacheStore(),
        "account:region:plugin",
        logger=logger,
    )

    assert logger.warnings[0][0] == "cache namespace delete failed"
    assert logger.warnings[0][1]["namespace"] == "account:region:plugin"
