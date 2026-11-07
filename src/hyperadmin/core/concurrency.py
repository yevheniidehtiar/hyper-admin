"""Optimistic concurrency control: version-field detection and the stale-write error.

Pure metadata inspection — no ORM, no HTTP. Adapters enforce the compare-and-set;
views translate :class:`StaleRecordError` into a 409. See ``docs/specs/realtime-occ.md``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from hyperadmin.core.schema import schema_for

_VERSION_FIELD = "version"
_UPDATED_AT_FIELD = "updated_at"
_OVERRIDE_ATTR = "__version_field__"


class ConcurrencyConfigurationError(ValueError):
    """Raised at startup when ``enforce_occ`` is set on a model with no version field."""


class StaleRecordError(Exception):
    """Raised by an adapter when a row changed since the caller read it.

    Args:
        model: The model class whose row was stale.
        pk: Primary key of the row.
        expected: The version the caller submitted.
        current: The version currently stored (``None`` if the row vanished).
    """

    def __init__(self, *, model: type, pk: Any, expected: Any, current: Any) -> None:
        self.model = model
        self.pk = pk
        self.expected = expected
        self.current = current
        super().__init__(
            f"Stale {model.__name__} {pk!r}: expected version {expected!r}, found {current!r}"
        )

    @property
    def expected_version(self) -> Any:
        """Alias of :attr:`expected`."""
        return self.expected

    @property
    def current_version(self) -> Any:
        """Alias of :attr:`current`."""
        return self.current


def _field_names(model: type) -> set[str]:
    names: set[str] = set(schema_for(model).model_fields)
    table = getattr(model, "__table__", None)
    if table is not None:
        names |= {column.key for column in table.columns}
    return names


def detect_version_field(model: type, *, use_updated_at: bool = False) -> str | None:
    """Return the field that serves as ``model``'s concurrency token, if any.

    Precedence: ``__version_field__`` class attribute, then a ``version`` field,
    then ``updated_at`` (only when ``use_updated_at`` is true).
    """
    explicit = getattr(model, _OVERRIDE_ATTR, None)
    if isinstance(explicit, str):
        return explicit
    names = _field_names(model)
    if _VERSION_FIELD in names:
        return _VERSION_FIELD
    if use_updated_at and _UPDATED_AT_FIELD in names:
        return _UPDATED_AT_FIELD
    return None


def resolve_version_field(
    model: type, *, enforce: bool, use_updated_at: bool = False
) -> str | None:
    """Resolve the version field for ``model`` honouring ``AdminOptions.enforce_occ``.

    Returns ``None`` when OCC is not enforced (legacy last-write-wins).

    Raises:
        ConcurrencyConfigurationError: ``enforce`` is true and no version field exists.
    """
    if not enforce:
        return None
    field = detect_version_field(model, use_updated_at=use_updated_at)
    if field is None:
        raise ConcurrencyConfigurationError(
            f"{model.__name__} sets enforce_occ=True but has no version field: add "
            f"`version: int`, declare `__version_field__`, or enable "
            f"HYPERADMIN_CONCURRENCY_USE_UPDATED_AT with an `updated_at` column"
        )
    return field


def next_version(field: str, current: Any) -> Any:
    """Return the value to store after a successful write.

    Timestamps are refreshed to now (UTC); everything else is incremented.
    """
    if field == _UPDATED_AT_FIELD or isinstance(current, datetime):
        return datetime.now(UTC)
    return int(current) + 1
