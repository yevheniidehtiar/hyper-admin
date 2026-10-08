"""Typed, whitelisted list filters.

Turns ``filter_<field>[__<op>]=<raw>`` query parameters into typed
:class:`FilterCondition` objects. Pure: it reads pydantic annotations only and
leaves building SQL clauses to the adapters.

Query syntax:

- ``filter_<f>=v`` and ``filter_<f>__exact=v`` — equality;
- ``filter_<f>__gte=v`` / ``filter_<f>__lte=v`` — inclusive bounds;
- ``filter_<f>__in=a,b`` (the parameter may also repeat) — membership;
- ``filter_<f>__isnull=true|false``.

A date-only value on a ``datetime`` field becomes whole-day bounds (an exact date
becomes the range ``[d 00:00, d 23:59:59.999999]``). On aware columns the bounds
are local days in the display timezone, converted to UTC.
"""

from __future__ import annotations

import logging
import re
import types
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone, tzinfo
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import AwareDatetime, NaiveDatetime

from hyperadmin.core.timezones import DateTimeKind, parse_datetime_input

logger = logging.getLogger(__name__)

FilterOp = Literal["exact", "gte", "lte", "in", "isnull"]
FILTER_OPS: frozenset[str] = frozenset({"exact", "gte", "lte", "in", "isnull"})
FILTER_PARAM_PREFIX = "filter_"
_OP_SEPARATOR = "__"
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off"})

DateTimeKindResolver = Callable[[str], "DateTimeKind | str | None"]
AnnotationResolver = Callable[[str], Any]


class FilterValueError(ValueError):
    """Raised when a raw filter value cannot be coerced to the field's type."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class FilterCondition:
    """One typed predicate: ``<field> <op> <value>``."""

    field: str
    op: FilterOp
    value: Any

    def __post_init__(self) -> None:
        if self.op not in FILTER_OPS:
            msg = f"Unknown filter operator {self.op!r}; expected one of {sorted(FILTER_OPS)}"
            raise ValueError(msg)


@dataclass
class ParsedFilters:
    """Result of :func:`parse_filter_params`.

    Attributes:
        conditions: Typed conditions to pass to the adapter.
        active: Raw values keyed by ``<field>`` or ``<field>__<op>``, to re-render inputs.
        errors: Messages keyed by field for values that could not be coerced.
    """

    conditions: list[FilterCondition] = field(default_factory=list)
    active: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


def _unwrap(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        members = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(members) == 1:
            return _unwrap(members[0])
    return annotation


def _is_datetime_type(annotation: Any) -> bool:
    if annotation is AwareDatetime or annotation is NaiveDatetime:
        return True
    return isinstance(annotation, type) and issubclass(annotation, datetime)


def _invalid(raw: str, kind: str, field_name: str | None) -> FilterValueError:
    target = f" for {field_name}" if field_name else ""
    return FilterValueError(f"Enter a valid {kind}{target}: {raw!r}", field=field_name)


def _coerce_bool(raw: str, field_name: str | None) -> bool:
    lowered = raw.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise _invalid(raw, "boolean", field_name)


def _coerce_enum(enum_type: type[Enum], raw: str, field_name: str | None) -> Enum:
    for member in enum_type:
        if str(member.value) == raw or member.name == raw:
            return member
    raise _invalid(raw, "choice", field_name)


def _coerce_decimal(raw: str, field_name: str | None) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise _invalid(raw, "number", field_name) from exc
    if not value.is_finite():
        raise _invalid(raw, "number", field_name)
    return value


def _coerce_datetime(raw: str, field_name: str | None) -> datetime:
    text = f"{raw[:-1]}+00:00" if raw.endswith(("Z", "z")) else raw
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise _invalid(raw, "date/time", field_name) from exc


def coerce_filter_value(annotation: Any, raw: str, *, field: str | None = None) -> Any:
    """Coerce a raw query-string value to ``annotation``.

    Supports ``bool``, ``int``, ``float``, ``Decimal``, ``UUID``, ``Enum``, ``date``,
    ``datetime`` and ``str`` (``Optional`` and ``Annotated`` are unwrapped). Other
    annotations return ``raw`` unchanged.

    Raises:
        FilterValueError: When ``raw`` does not parse; ``field`` names the field.
    """
    target = _unwrap(annotation)
    text = raw.strip()
    simple: dict[Any, tuple[Callable[[str], Any], str]] = {
        int: (int, "whole number"),
        float: (float, "number"),
        uuid.UUID: (uuid.UUID, "UUID"),
        date: (date.fromisoformat, "date"),
    }
    if target is bool:
        return _coerce_bool(text, field)
    if _is_datetime_type(target):
        return _coerce_datetime(text, field)
    if target is Decimal:
        return _coerce_decimal(text, field)
    if isinstance(target, type) and issubclass(target, Enum):
        return _coerce_enum(target, text, field)
    if target in simple:
        parser, kind = simple[target]
        try:
            return parser(text)
        except ValueError as exc:
            raise _invalid(raw, kind, field) from exc
    return raw


def normalize_filters(
    filters: Mapping[str, Any] | Sequence[FilterCondition] | None,
) -> list[FilterCondition]:
    """Return ``filters`` as a list of conditions; a legacy dict means equality.

    Raises:
        TypeError: When a sequence contains something other than ``FilterCondition``.
    """
    if filters is None:
        return []
    if isinstance(filters, Mapping):
        return [FilterCondition(name, "exact", value) for name, value in filters.items()]
    conditions: list[Any] = list(filters)
    for item in conditions:
        if not isinstance(item, FilterCondition):
            msg = f"Expected FilterCondition, got {type(item).__name__}"
            raise TypeError(msg)
    return conditions


def _iter_params(params: Any) -> Iterable[tuple[str, str]]:
    if hasattr(params, "multi_items"):
        yield from params.multi_items()
        return
    items = params.items() if isinstance(params, Mapping) else params
    for key, value in items:
        if isinstance(value, (list, tuple)):
            for item in value:
                yield key, item
        else:
            yield key, value


def _split_key(key: str) -> tuple[str, FilterOp]:
    name = key[len(FILTER_PARAM_PREFIX) :]
    head, sep, tail = name.rpartition(_OP_SEPARATOR)
    if sep and head and tail in FILTER_OPS:
        return head, tail  # type: ignore[return-value]
    return name, "exact"


def _day_bounds(raw: str, kind: str, tz: tzinfo) -> tuple[datetime, datetime]:
    """Return the whole-day bounds for ``raw``.

    Raises:
        ValueError: For an invalid date; ``OverflowError`` near ``date.min``/``max``
            on aware columns (callers treat both as invalid input).
    """
    day = date.fromisoformat(raw)
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    if kind == "aware":
        start = start.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
        end = end.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
    return start, end


class _FieldContext:
    """Annotation and timezone facts for one field, used while parsing."""

    def __init__(self, name: str, annotation: Any, kind: str, tz: tzinfo) -> None:
        self.name = name
        self.annotation = annotation
        self.is_datetime = _is_datetime_type(_unwrap(annotation))
        self.kind = kind
        self.tz = tz

    def coerce(self, raw: str) -> Any:
        if not self.is_datetime:
            return coerce_filter_value(self.annotation, raw, field=self.name)
        text = raw.strip()
        try:
            if _DATE_ONLY.match(text):
                return _day_bounds(text, self.kind, self.tz)[0]
            kind: DateTimeKind = "aware" if self.kind == "aware" else "naive"
            return parse_datetime_input(text, kind=kind, tz=self.tz)
        except (ValueError, OverflowError) as exc:
            raise _invalid(raw, "date/time", self.name) from exc

    def conditions(self, op: FilterOp, raws: list[str]) -> list[FilterCondition]:
        if op == "isnull":
            return [FilterCondition(self.name, op, _coerce_bool(raws[0].strip(), self.name))]
        if op == "in":
            return [FilterCondition(self.name, op, tuple(self.coerce(raw) for raw in raws))]
        raw = raws[0].strip()
        if self.is_datetime and _DATE_ONLY.match(raw) and op in ("exact", "lte"):
            try:
                start, end = _day_bounds(raw, self.kind, self.tz)
            except (ValueError, OverflowError) as exc:
                raise _invalid(raw, "date", self.name) from exc
            if op == "lte":
                return [FilterCondition(self.name, "lte", end)]
            return [
                FilterCondition(self.name, "gte", start),
                FilterCondition(self.name, "lte", end),
            ]
        return [FilterCondition(self.name, op, self.coerce(raw))]


def _collect_raw_values(
    params: Any, allowed_set: set[str]
) -> dict[tuple[str, FilterOp], list[str]]:
    grouped: dict[tuple[str, FilterOp], list[str]] = {}
    for key, value in _iter_params(params):
        if not key.startswith(FILTER_PARAM_PREFIX) or value in (None, ""):
            continue
        name, op = _split_key(key)
        if name not in allowed_set:
            logger.debug("Ignoring filter on non-whitelisted field %r", name)
            continue
        values = str(value).split(",") if op == "in" else [str(value)]
        grouped.setdefault((name, op), []).extend(v.strip() for v in values if v.strip())
    return grouped


def parse_filter_params(
    model: Any,
    params: Any,
    allowed: Iterable[str],
    *,
    tz: tzinfo = timezone.utc,
    datetime_kind: DateTimeKindResolver | None = None,
    annotation_of: AnnotationResolver | None = None,
) -> ParsedFilters:
    """Parse ``filter_*`` query parameters into typed conditions.

    Args:
        model: A pydantic/SQLModel class; its ``model_fields`` provide annotations.
            Fields it does not declare are ignored. Classes without ``model_fields``
            pass raw string values through.
        params: Query parameters: Starlette ``QueryParams`` (``multi_items``), a
            mapping (values may be lists) or an iterable of ``(key, value)`` pairs.
        allowed: Whitelisted field names (``list_filter``). Others are ignored.
        tz: Display timezone used to localise datetime input on aware columns.
        datetime_kind: Resolves a field to ``"aware"`` or ``"naive"`` (typically
            ``adapter.datetime_kind``). Defaults to naive.
        annotation_of: Resolves a field to the type its values coerce to (an
            adapter passes the mapped column's ``python_type``). ``None`` from the
            resolver falls back to ``model_fields``, then to ``str``. Needed for
            plain SQLAlchemy models, which have no ``model_fields``.

    Returns:
        The conditions, the active raw values and per-field error messages. A
        value that cannot be coerced drops its condition and records an error.
    """
    model_fields = getattr(model, "model_fields", None)
    result = ParsedFilters()
    for (name, op), raws in _collect_raw_values(params, set(allowed)).items():
        if not raws:
            continue
        annotation = annotation_of(name) if annotation_of else None
        if annotation is None:
            if isinstance(model_fields, Mapping):
                if name not in model_fields:
                    logger.debug("Ignoring filter on unknown field %r", name)
                    continue
                annotation = model_fields[name].annotation
            else:
                annotation = str
        kind = (datetime_kind(name) if datetime_kind else None) or (
            "aware" if _unwrap(annotation) is AwareDatetime else "naive"
        )
        active_key = name if op == "exact" else f"{name}{_OP_SEPARATOR}{op}"
        result.active[active_key] = ",".join(raws)
        try:
            result.conditions.extend(_FieldContext(name, annotation, kind, tz).conditions(op, raws))
        except FilterValueError as exc:
            result.errors[name] = str(exc)
    return result
