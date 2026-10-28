"""``FilterDef``: the contract every list filter implements (filter library SDD).

A filter is a small, immutable declaration bound to one model field. It knows
three things: which querystring keys it reads (:meth:`FilterDef.parse`), how
the parsed values become typed :class:`~hyperadmin.core.filtering.FilterCondition`
objects (:meth:`FilterDef.compile`), and how it renders in the filter sidebar
(:meth:`FilterDef.render`). Compiling goes through
:func:`hyperadmin.core.filtering.parse_filter_params`, so a filter never builds
SQL and the v0.5.8 whitelist stays the only path from user input to the query.

Per-request facts (the model, the display timezone, today's date, the current
user) travel in a :class:`FilterBinding`; what the sidebar needs on top of that
(the querystring, prefetched choices, a template environment) travels in a
:class:`FilterRenderContext`.
"""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, select_autoescape

from hyperadmin.core.filtering import FILTER_PARAM_PREFIX, parse_filter_params
from hyperadmin.core.schema import schema_for

if TYPE_CHECKING:
    from hyperadmin.core.choices import ChoiceItem
    from hyperadmin.core.filtering import DateTimeKindResolver, FilterCondition

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_TRUE = frozenset({"1", "true", "yes", "on"})


def query_values(qs: Any, key: str) -> list[str]:
    """Return every non-blank value of ``key`` in ``qs``, stripped, in order.

    ``qs`` may be a Starlette ``QueryParams`` (``getlist``), a mapping whose
    values are strings or lists of strings, or ``None``.
    """
    if qs is None:
        return []
    if hasattr(qs, "getlist"):
        raws: Any = qs.getlist(key)
    elif isinstance(qs, Mapping):
        value = qs.get(key)
        raws = [] if value is None else value if isinstance(value, (list, tuple)) else [value]
    else:
        raws = []
    return [text for text in (str(raw).strip() for raw in raws) if text]


def query_value(qs: Any, key: str) -> str | None:
    """Return the last non-blank value of ``key`` in ``qs``, or ``None``."""
    values = query_values(qs, key)
    return values[-1] if values else None


def is_truthy(raw: str | None) -> bool:
    """``True`` for ``1``/``true``/``yes``/``on`` (case-insensitive)."""
    return raw is not None and raw.strip().lower() in _TRUE


def query_pairs(qs: Any) -> list[tuple[str, str]]:
    """``qs`` flattened to ``(key, value)`` pairs, repeated keys kept in order."""
    if qs is None:
        return []
    if hasattr(qs, "multi_items"):
        return [(str(k), str(v)) for k, v in qs.multi_items()]
    pairs: list[tuple[str, str]] = []
    if isinstance(qs, Mapping):
        for key, value in qs.items():
            values = value if isinstance(value, (list, tuple)) else [value]
            pairs.extend((str(key), str(v)) for v in values if v is not None)
    return pairs


def clear_href(qs: Any, keys: Sequence[str], extra: Mapping[str, str] | None = None) -> str:
    """A relative ``?...`` href that drops ``keys`` (and ``page``) from ``qs``, adds ``extra``."""
    pairs = [(k, v) for k, v in query_pairs(qs) if k not in keys and k != "page"]
    pairs.extend((extra or {}).items())
    return f"?{urlencode(pairs)}"


@functools.lru_cache(maxsize=1)
def default_environment() -> Environment:
    """A Jinja environment over the package templates, used when no admin env is given."""
    from hyperadmin.i18n import install_jinja_i18n  # noqa: PLC0415 — keep the import light

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    install_jinja_i18n(env)
    return env


@dataclass(frozen=True, kw_only=True)
class FilterBinding:
    """Per-request facts a filter needs to compile and to resolve defaults.

    Args:
        model: The admin model; its annotations type the compiled values. ``None``
            falls back to each filter's own ``value_type``.
        tz: Display timezone: date bounds on aware columns are local days in it.
        today: "Today" for presets and period defaults; defaults to today in ``tz``.
        datetime_kind: Resolves a field to ``"aware"``/``"naive"`` (``adapter.datetime_kind``).
        user: The current user, or ``None`` when anonymous.
        user_key: ``request.state.user_key`` — what owner columns are compared to.
    """

    model: Any = None
    tz: tzinfo = timezone.utc
    today: date | None = None
    datetime_kind: DateTimeKindResolver | None = None
    user: Any = None
    user_key: Any = None

    @property
    def today_date(self) -> date:
        """``today`` when given, else the current date in ``tz``."""
        return self.today or datetime.now(self.tz).date()


@dataclass(frozen=True, kw_only=True)
class FilterRenderContext:
    """What :meth:`FilterDef.render` needs beyond the filter itself.

    Args:
        query: The request querystring (``QueryParams`` or a mapping).
        binding: Per-request facts (see :class:`FilterBinding`).
        choices: Prefetched options for relation/choice filters (``ChoiceItem`` dicts).
        more: Number of further options not in ``choices`` ("Show N more" link).
        templates: The admin's Jinja environment; defaults to the package templates.
    """

    query: Any = None
    binding: FilterBinding = field(default_factory=FilterBinding)
    choices: Sequence[ChoiceItem] = ()
    more: int = 0
    templates: Environment | None = None


@dataclass(frozen=True, kw_only=True)
class FilterDef(ABC):
    """Base class for every list filter.

    Subclasses declare ``template`` (a partial under ``components/filters/``),
    ``value_type`` (the Python type raw values coerce to when the model does not
    declare the field) and implement :meth:`parse` and :meth:`compile`.

    Args:
        field: The model column the filter binds to.
        label: Sidebar heading; defaults to the field name, title-cased.
    """

    template: ClassVar[str]
    value_type: ClassVar[Any] = str

    field: str
    label: str | None = None

    @property
    def slug(self) -> str:
        """URL-safe key naming this filter in test ids and errors; defaults to ``field``."""
        return self.field

    @property
    def title(self) -> str:
        """The label to show, with a title-cased fallback from ``field``."""
        return self.label or self.field.replace("_", " ").title()

    @property
    def query_keys(self) -> tuple[str, ...]:
        """Querystring keys this filter reads (and a "Clear" link drops)."""
        return (self.field,)

    @abstractmethod
    def parse(self, qs: Any) -> dict[str, Any]:
        """Extract this filter's values from the querystring; ``{}`` when inactive or invalid."""

    @abstractmethod
    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        """Turn :meth:`parse` output into typed conditions for the adapter."""

    def error(self, qs: Any) -> str | None:  # noqa: ARG002 — hook; most filters never fail
        """A message for invalid input in ``qs``, or ``None``."""
        return None

    def describe(self, parsed: dict[str, Any]) -> str | None:  # noqa: ARG002 — hook
        """Chip text for the applied filter, or ``None`` when inactive."""
        return None

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        """Template variables for :attr:`template`; subclasses extend this."""
        parsed = self.parse(ctx.query)
        return {
            "filter": self,
            "parsed": parsed,
            "active": bool(parsed),
            "error": self.error(ctx.query),
            "clear_href": clear_href(ctx.query, self.query_keys),
        }

    def render(self, ctx: FilterRenderContext) -> str:
        """Render the sidebar group for this filter."""
        env = ctx.templates or default_environment()
        return env.get_template(self.template).render(**self.context(ctx))

    def typed_conditions(
        self,
        binding: FilterBinding | None,
        params: Mapping[str, str | Sequence[str]],
    ) -> list[FilterCondition]:
        """Coerce ``params`` through the typed pipeline for :attr:`field`.

        ``params`` maps an operator suffix (``""`` for exact, ``"gte"``,
        ``"lte"``, ``"in"``) to the raw value(s). The model's annotation types
        the values; without one the filter's ``value_type`` does. Values that
        fail to coerce are dropped, like any other bad querystring input.
        """
        binding = binding or FilterBinding()
        try:
            declared = self.field in schema_for(binding.model).model_fields
        except TypeError:  # no model bound, or a class the registry has no schema for
            declared = False
        raw_params = {
            f"{FILTER_PARAM_PREFIX}{self.field}{'__' + suffix if suffix else ''}": value
            for suffix, value in params.items()
        }
        return parse_filter_params(
            binding.model,
            raw_params,
            [self.field],
            tz=binding.tz,
            datetime_kind=binding.datetime_kind,
            annotation_of=None if declared else (lambda _name: self.value_type),
        ).conditions
