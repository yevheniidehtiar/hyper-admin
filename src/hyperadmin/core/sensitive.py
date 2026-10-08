"""Sensitive-field detection.

A sensitive field (a password hash, an API secret, a token) must never become a
query oracle: it is excluded from inferred search and list columns, from URL
filters, from sorting, from relation labels and from the detail page, and forms
treat it as write-only. See ``docs/specs/bring-your-own-app.md`` section D.3.

Mark a field explicitly with the marker in its JSON schema extra. With SQLModel
(whose ``Field()`` has no ``json_schema_extra`` argument) write::

    api_key: str = Field(schema_extra={"json_schema_extra": {"hyperadmin_sensitive": True}})

and with plain Pydantic::

    api_key: str = Field(json_schema_extra={"hyperadmin_sensitive": True})

This module is a pure utility: it MUST NOT import from ``views/``, ``auth/`` or
``adapters/``.
"""

from __future__ import annotations

import re
import types
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Union, get_args, get_origin

#: The JSON-schema-extra key that marks a field as sensitive (see module docstring).
SENSITIVE_MARKER = "hyperadmin_sensitive"

_SENSITIVE_NAME = re.compile(r"(^|_)(password|secret|token|hash)(_|$)", re.IGNORECASE)

#: Maps a model class to its admin's ``AdminOptions.sensitive_fields`` (or ``None``).
SensitiveOverridesResolver = Callable[[Any], "Mapping[str, bool] | None"]

_OVERRIDES_RESOLVER: ContextVar[SensitiveOverridesResolver | None] = ContextVar(
    "hyperadmin_sensitive_overrides", default=None
)


def is_text_annotation(annotation: Any) -> bool:
    """Return whether ``annotation`` is ``str`` or ``bytes`` (optionally ``Optional``)."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return len(args) == 1 and is_text_annotation(args[0])
    return isinstance(annotation, type) and issubclass(annotation, (str, bytes))


def is_sensitive(
    name: str,
    field_info: Any = None,
    overrides: Mapping[str, bool] | None = None,
) -> bool:
    """Return whether the field ``name`` holds a secret.

    A field is sensitive when it carries the ``hyperadmin_sensitive`` marker
    (see the module docstring), or when it is a text field (``str`` / ``bytes``)
    whose name matches ``(^|_)(password|secret|token|hash)(_|$)``. The name
    heuristic never applies to booleans, numbers, enums or relations
    (``is_secret: bool`` is a flag, not a secret); mark those explicitly.
    ``overrides`` (``AdminOptions.sensitive_fields``) wins in either direction.

    Args:
        name: The field name.
        field_info: The Pydantic ``FieldInfo``, used to read the explicit marker
            and the annotation. Without it only the name is considered.
        overrides: Mapping of field name to a forced sensitive flag.
    """
    if overrides and name in overrides:
        return bool(overrides[name])
    extra = getattr(field_info, "json_schema_extra", None)
    if isinstance(extra, Mapping) and SENSITIVE_MARKER in extra:
        return bool(extra[SENSITIVE_MARKER])
    if field_info is not None and not is_text_annotation(getattr(field_info, "annotation", str)):
        return False
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


@contextmanager
def sensitive_overrides_scope(resolver: SensitiveOverridesResolver) -> Iterator[None]:
    """Make each model's admin overrides visible to code that only sees the model.

    Adapters, relation labels and the choices search only know the model class.
    Inside this scope, :func:`effective_sensitive_field_names` also applies the
    ``AdminOptions.sensitive_fields`` that ``resolver`` returns for that model.
    The resolver lives in a ``ContextVar`` so concurrent requests never share it.
    """
    token = _OVERRIDES_RESOLVER.set(resolver)
    try:
        yield
    finally:
        _OVERRIDES_RESOLVER.reset(token)


def effective_sensitive_field_names(model: Any) -> set[str]:
    """Return the sensitive fields of ``model``, including its admin's overrides.

    Outside a :func:`sensitive_overrides_scope`, only the marker and the name
    heuristic apply.
    """
    resolver = _OVERRIDES_RESOLVER.get()
    overrides = resolver(model) if resolver is not None else None
    return sensitive_field_names(model, overrides or None)
