"""Form layout configuration for HyperAdmin."""

from __future__ import annotations

from enum import Enum


class FormLayout(str, Enum):
    """Controls the column layout of form fields.

    Attributes:
        SINGLE: Default single-column layout (one field per row).
        TWO_COLUMN: Two-column grid layout (fields arranged in two columns).
    """

    SINGLE = "single"
    TWO_COLUMN = "two-column"
