"""Application settings loaded from files and environment."""

from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from pydantic import Field, RedisDsn, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from aperture.models.plugin_config import PluginConfig


class Settings(BaseSettings):
    """All settings used by the Aperture service."""

    listen_addr: IPv4Address = Field(
        default=IPv4Address("127.0.0.1"),
        description="IP address used by the HTTP server.",
    )
    port: int = Field(
        default=8000,
        description="TCP port used by the HTTP server.",
    )
    log_level: str = Field(
        default="info",
        description="Log level used by the service.",
    )
    redis_url: RedisDsn = Field(
        default=RedisDsn("redis://127.0.0.1:6379"),
        description="Redis URL used when the Redis cache backend is enabled.",
    )
    cache_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description="Cache backend used by the service.",
    )
    cache_default_ttl_seconds: int = Field(
        default=300,
        description="Default cache TTL in seconds.",
    )
    plugins: dict[str, PluginConfig] = Field(
        default_factory=lambda: {
            "admin": PluginConfig(
                module="aperture.plugins.admin.main",
                prefix="/admin",
            )
        },
        description="Plugins that Aperture loads at startup.",
    )

    auth_mode: Literal["off", "api_key"] = Field(
        default="off",
        description="Authentication mode used by the API.",
    )
    api_keys: dict[str, str] = Field(
        default_factory=dict,
        description="Known API keys, stored as service name to key.",
    )
    api_key_header: str = Field(
        default="X-API-Key",
        description="HTTP header that carries the API key.",
    )
    auth_skip_paths: list[str] = Field(
        default_factory=lambda: ["/", "/docs", "/openapi.json", "/livez", "/readyz"],
        description="Paths that do not require authentication.",
    )

    model_config = SettingsConfigDict(
        env_prefix="APT_",
        env_nested_delimiter="__",
        yaml_file=["settings.yml", "settings.yaml"],
        env_file=".env",
        extra="ignore",
    )

    @field_validator("cache_default_ttl_seconds")
    @classmethod
    def cache_ttl_must_be_positive(cls, value: int) -> int:
        """Reject a cache TTL that cannot expire in the future."""

        if value <= 0:
            msg = "cache_default_ttl_seconds must be positive"
            raise ValueError(msg)
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Let init values and envvars override YAML files."""

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


def load_settings(path: str | Path | None = None) -> Settings:
    """Load settings from the default places or from one YAML file."""

    if path is None:
        return Settings()

    previous_yaml_file = Settings.model_config.get("yaml_file")
    Settings.model_config["yaml_file"] = [str(path)]
    try:
        return Settings()
    finally:
        Settings.model_config["yaml_file"] = previous_yaml_file
