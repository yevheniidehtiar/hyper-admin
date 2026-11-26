"""Search-column detection shared by the SQLModel and SQLAlchemy adapters."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, literal
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.sql.sqltypes import Enum, String
from sqlalchemy.sql.visitors import InternalTraversal
from sqlmodel import AutoString

from hyperadmin.core.sensitive import effective_sensitive_field_names


class _Contains(ColumnElement[bool]):
    """``column ILIKE pattern``, compiled as a plain ``LIKE`` on SQLite.

    SQLAlchemy renders ``ilike`` on SQLite as ``lower(column) LIKE lower(pattern)``. SQLite's
    ``LIKE`` already ignores ASCII case and its built-in ``lower()`` folds ASCII only, so both
    match the same rows. But ``lower()`` builds a new string for every row it scans, and on a
    large table concurrent scans then slow each other down: on 900,000 rows one scan took
    89 ms alone and 1.4 s each with five at once, while plain ``LIKE`` stayed near 40 ms.
    """

    inherit_cache = True
    type = Boolean()
    _is_implicitly_boolean = True  # a comparison: no "= 1" in WHERE on SQLite and MySQL
    _traverse_internals = [  # noqa: RUF012 - SQLAlchemy's cache key reads this list
        ("column", InternalTraversal.dp_clauseelement),
        ("pattern", InternalTraversal.dp_clauseelement),
    ]

    def __init__(self, column: Any, pattern: Any) -> None:
        self.column = column
        self.pattern = pattern


@compiles(_Contains)
def _compile_contains(element: _Contains, compiler: Any, **kw: Any) -> str:
    return str(compiler.process(element.column.ilike(element.pattern), **kw))


@compiles(_Contains, "sqlite")
def _compile_contains_sqlite(element: _Contains, compiler: Any, **kw: Any) -> str:
    return str(compiler.process(element.column.like(element.pattern), **kw))


def contains_clause(column: Any, text: str) -> Any:
    """Return a case-insensitive substring match of ``text`` on ``column``.

    ``ILIKE`` where the database has it; on SQLite a plain ``LIKE``, which already ignores
    ASCII case (see :class:`_Contains`).

    The pattern is bound as a plain ``String``. Left to itself SQLAlchemy coerces it to the
    column's type, which runs a ``TypeDecorator``'s bind processor on free text: a validating
    or encrypting type then raises, or compares against the wrong value.
    """
    return _Contains(column, literal(f"%{text}%", String))


def detect_search_columns(model: Any, mapper: Any) -> list[str]:
    """Return the non-primary-key string columns of ``model`` that are not sensitive.

    Used when no explicit ``search_fields`` are configured. Sensitive columns
    (``password_hash``, tokens, ...) are never searched: a substring search on
    them would leak their value one character at a time. Inside a request, the
    model admin's ``AdminOptions.sensitive_fields`` overrides apply too.

    ``Enum`` subclasses ``String`` but is skipped: PostgreSQL has no ``ILIKE`` for
    native enum types, and the stored member names are not what users type anyway.
    """
    if mapper is None:
        return []
    sensitive = effective_sensitive_field_names(model)
    return [
        col.key
        for col in mapper.columns
        if isinstance(col.type, (String, AutoString))
        and not isinstance(col.type, Enum)
        and not col.primary_key
        and col.key not in sensitive
    ]
