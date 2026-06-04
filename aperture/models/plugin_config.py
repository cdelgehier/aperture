"""Models for plugin configuration."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PluginConfig(BaseModel):
    """Settings for one plugin loaded by Aperture."""

    enabled: bool = Field(
        default=True,
        description="Set to false to skip this plugin.",
    )
    module: str | None = Field(
        default=None,
        description="Python module path that contains the plugin router factory.",
    )
    prefix: str = Field(
        default="",
        description="URL prefix used when the plugin is mounted.",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Free plugin settings passed to the plugin at startup.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        """Make plugin mount paths stable and easy to join."""

        if not value:
            return ""
        prefixed = value if value.startswith("/") else f"/{value}"
        return prefixed.rstrip("/")
