"""Fieldset specification for grouping form fields."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FieldsetSpec:
    """Defines a group of fields rendered together under a collapsible heading.

    Attributes:
        name: Display label for the fieldset heading.
        fields: Ordered list of field names belonging to this group.
        collapsed: Whether the fieldset starts in a collapsed state.
        description: Optional help text shown below the heading.
    """

    name: str
    fields: list[str] = field(default_factory=list)
    collapsed: bool = False
    description: str | None = None
