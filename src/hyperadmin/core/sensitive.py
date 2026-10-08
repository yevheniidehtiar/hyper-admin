"""Sensitive-field detection.

A sensitive field (a password hash, an API secret, a token) must never become a
query oracle: it is excluded from inferred search and list columns, from URL
filters, from sorting and from the detail page, and forms treat it as
write-only. See ``docs/specs/bring-your-own-app.md`` section D.3.

This module is a pure utility: it MUST NOT import from ``views/``, ``auth/`` or
``adapters/``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

#: ``Field(json_schema_extra={SENSITIVE_MARKER: True})`` marks a field as sensitive.
SENSITIVE_MARKER = "hyperadmin_sensitive"

_SENSITIVE_NAME = re.compile(r"(^|_)(password|secret|token|hash)(_|$)", re.IGNORECASE)


def is_sensitive(
    name: str,
    field_info: Any = None,
    overrides: Mapping[str, bool] | None = None,
) -> bool:
    """Return whether the field ``name`` holds a secret.

    A field is sensitive when it sets ``json_schema_extra={"hyperadmin_sensitive": True}``
    or its name matches ``(^|_)(password|secret|token|hash)(_|$)``.
    ``overrides`` (``AdminOptions.sensitive_fields``) wins in either direction.

    Args:
        name: The field name.
        field_info: The Pydantic ``FieldInfo``, used to read the explicit marker.
        overrides: Mapping of field name to a forced sensitive flag.
    """
    if overrides and name in overrides:
        return bool(overrides[name])
    extra = getattr(field_info, "json_schema_extra", None)
    if isinstance(extra, Mapping) and SENSITIVE_MARKER in extra:
        return bool(extra[SENSITIVE_MARKER])
    return bool(_SENSITIVE_NAME.search(name))


def sensitive_field_names(model: Any, overrides: Mapping[str, bool] | None = None) -> set[str]:
    """Return the names of every sensitive field on ``model``.

    Considers the model's Pydantic ``model_fields`` and, for ORM models, its
    mapped column keys (columns that are not exposed as Pydantic fields).
    """
    fields: dict[str, Any] = dict(getattr(model, "model_fields", {}) or {})
    try:
        from sqlalchemy import inspect as sa_inspect  # noqa: PLC0415

        mapper: Any = sa_inspect(model, raiseerr=False)
        if mapper is not None:
            for column in getattr(mapper, "columns", []):
                fields.setdefault(column.key, None)
    except Exception:  # noqa: S110 — plain Pydantic models have no mapper
        pass
    names = {name for name, info in fields.items() if is_sensitive(name, info, overrides)}
    if overrides:
        names |= {name for name, flag in overrides.items() if flag}
    return names
