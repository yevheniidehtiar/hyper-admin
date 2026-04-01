"""File upload metadata for classify_field() integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FileFieldMeta:
    """Metadata returned by ``classify_field()`` for file/image columns.

    Attributes:
        is_image: ``True`` when the column is an ``ImageType``.
    """

    is_image: bool = False
