from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict


class ChoiceItem(TypedDict):
    """A single choice for a select field."""

    value: str
    label: str
    selected: bool


class ChoicesProvider(Protocol):
    """Protocol for providing choices to a field."""

    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> list[ChoiceItem]:
        """Retrieves a list of choices based on the provided parameters."""
        ...


@dataclass
class SelectFieldMeta:
    """Metadata for a select field to hint the widget layer."""

    choices_source: Literal["enum", "static", "relation"]
    preload: bool = True
    multiple: bool = False
    searchable: bool = False
    dependent_on: str | None = None
