"""Search-column detection shared by the SQLModel and SQLAlchemy adapters."""

from __future__ import annotations

from typing import Any

from sqlalchemy.sql.sqltypes import String
from sqlmodel import AutoString

from hyperadmin.core.sensitive import sensitive_field_names


def detect_search_columns(model: Any, mapper: Any) -> list[str]:
    """Return the non-primary-key string columns of ``model`` that are not sensitive.

    Used when no explicit ``search_fields`` are configured. Sensitive columns
    (``password_hash``, tokens, ...) are never searched: a substring search on
    them would leak their value one character at a time.
    """
    if mapper is None:
        return []
    sensitive = sensitive_field_names(model)
    return [
        col.key
        for col in mapper.columns
        if isinstance(col.type, (String, AutoString))
        and not col.primary_key
        and col.key not in sensitive
    ]
