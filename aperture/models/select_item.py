"""Models used by public select endpoints."""

from pydantic import BaseModel, ConfigDict


class SelectItem(BaseModel):
    """One item that can be shown in a select field."""

    model_config = ConfigDict(extra="forbid")

    label: str
    value: str
