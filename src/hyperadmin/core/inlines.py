"""Inline model specification for editing related models in the same form."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InlineModelSpec:
    """Defines a related model to be edited inline within the parent form.

    Attributes:
        model: The related SQLModel/Pydantic model class.
        fk_field: The foreign key field name on the related model that
            points back to the parent model (e.g. ``"order_id"``).
        fields: Ordered list of field names to display in each inline row.
            When empty, all non-PK/non-FK fields are shown.
        max_num: Maximum number of inline rows allowed (0 = unlimited).
        extra: Number of empty rows to display by default.
        title: Display label for the inline section. Defaults to the
            related model's class name.
    """

    model: Any
    fk_field: str
    fields: list[str] = field(default_factory=list)
    max_num: int = 0
    extra: int = 1
    title: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            name = getattr(self.model, "__name__", str(self.model))
            self.title = name + "s"

    @property
    def model_name(self) -> str:
        """Return the lowercase model class name."""
        return getattr(self.model, "__name__", str(self.model)).lower()

    def get_display_fields(self) -> list[str]:
        """Return the list of field names to show in each inline row.

        If ``fields`` is empty, introspects the model and returns all
        fields except ``id`` and the FK field.
        """
        if self.fields:
            return self.fields
        model_fields = getattr(self.model, "model_fields", {})
        return [name for name in model_fields if name != "id" and name != self.fk_field]
