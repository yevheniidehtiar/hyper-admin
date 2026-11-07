"""Jinja template filters shared across HyperAdmin templates.

These are pk-agnostic and timezone-aware replacements for the historical
``item.id`` / raw-datetime template code (BYOA SDD section A.9):

- ``ha_pk`` reads a row's primary key from a dict (``_pk`` first) or a model
  instance, the same lookup ``PrimaryKeyInfo.value_of`` uses.
- ``ha_dom_token`` turns any key into a value that is safe inside a DOM id or
  a ``data-testid`` attribute.
- ``ha_datetime_input`` and ``ha_display`` localise datetimes for, respectively,
  a ``datetime-local`` form input and read-only display, using the timezone
  resolved by :func:`resolve_tz`. ``ha_display`` also renders enum members by
  their label.

Registration is pure Jinja plumbing: :func:`register_template_filters` adds
the filters (and the default display timezone) to a ``jinja2.Environment``.
It takes no HTTP or ORM imports, so it stays usable outside a request.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime, tzinfo
from datetime import timezone as dt_timezone
from decimal import Decimal
from enum import Enum
from hashlib import blake2b
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from babel import Locale, UnknownLocaleError
from babel.numbers import format_currency, format_decimal
from jinja2 import pass_context
from markupsafe import Markup

from hyperadmin.core.display import get_enum_label
from hyperadmin.core.timezones import format_datetime_input, to_display

if TYPE_CHECKING:
    from jinja2 import Environment
    from jinja2.runtime import Context

logger = logging.getLogger(__name__)

#: Jinja global name used to carry the admin's configured display timezone
#: into :func:`resolve_tz` when no per-request override is set.
TIMEZONE_GLOBAL = "hyperadmin_timezone"

#: Jinja global name used to carry the admin's configured ``datetime_format``
#: (``Admin``'s ``settings.datetime_format``) into :func:`ha_display`.
DATETIME_FORMAT_GLOBAL = "hyperadmin_datetime_format"

_DOM_TOKEN_RE = re.compile(r"[A-Za-z0-9_.:-]+")
_DEFAULT_DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"


def ha_pk(item: Any, pk_attr: str = "id") -> Any:
    """Return ``item``'s primary key, for both a row ``dict`` and a model instance.

    Mirrors ``PrimaryKeyInfo.value_of``: a mapping is read through its ``_pk``
    key first (list rows set this), falling back to ``pk_attr``; anything else
    is read with ``getattr``.
    """
    if isinstance(item, Mapping):
        return item.get("_pk", item.get(pk_attr))
    return getattr(item, pk_attr, None)


def ha_dom_token(value: Any) -> str:
    """Return a DOM-id/``data-testid``-safe token for ``value``.

    A value already made only of ``[A-Za-z0-9_.:-]`` (every int and UUID key)
    is returned unchanged, as text. Anything else — a natural key containing
    spaces, slashes or other punctuation — is replaced by a stable short hash
    so it can never break an id or attribute value.
    """
    text = str(value)
    if _DOM_TOKEN_RE.fullmatch(text):
        return text
    digest = blake2b(text.encode(), digest_size=6).hexdigest()
    return f"h{digest}"


def resolve_tz(ctx: Context) -> tzinfo:
    """Resolve the display timezone for the current template render.

    Reads ``request.state.hyperadmin_timezone`` first (a host middleware or
    the auth bridge may set it, as an IANA zone name or a ``tzinfo``), then
    falls back to the timezone :func:`register_template_filters` registered
    as the ``hyperadmin_timezone`` Jinja global (``Admin``'s
    ``settings.timezone``). Defaults to UTC if neither is set.

    A per-request override that names an unknown or malformed IANA zone
    (a stale user-profile value, for example) is logged and ignored rather
    than raised — it falls back to the registered default — so one bad
    value cannot turn every ``ha_display``/``ha_datetime_input`` render into
    a 500.
    """
    return request_tz(ctx.get("request"), ctx.get(TIMEZONE_GLOBAL))


def request_tz(request: Any, default: Any = None) -> tzinfo:
    """Resolve the display timezone for ``request`` outside a template render.

    Same rules as :func:`resolve_tz`: ``request.state.hyperadmin_timezone``
    wins (an invalid zone name is logged and ignored), then ``default`` (the
    registered ``hyperadmin_timezone`` global / the admin's configured
    timezone), then UTC when ``default`` is not a ``tzinfo``. Views use it to
    localise user input: date filters on aware columns and datetime form fields.
    """
    default = default if isinstance(default, tzinfo) else dt_timezone.utc
    override = getattr(getattr(request, "state", None), "hyperadmin_timezone", None)
    if not override:
        return default
    if not isinstance(override, str):
        return override
    try:
        return ZoneInfo(override)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            "Ignoring invalid request.state.hyperadmin_timezone %r; falling back to %s",
            override,
            default,
        )
        return default


@pass_context
def ha_datetime_input(ctx: Context, value: Any) -> str:
    """Format ``value`` for a ``datetime-local`` input in the resolved timezone."""
    return format_datetime_input(value, resolve_tz(ctx))


@pass_context
def ha_timezone_name(ctx: Context) -> str:
    """Return the name of the resolved display timezone (a Jinja global).

    An IANA zone renders as its key (``Europe/Amsterdam``) and UTC as ``UTC``.
    The ``datetime_input`` widget shows it as a hint next to the input, so the
    operator knows which zone a naive ``datetime-local`` value is entered in.
    """
    return str(resolve_tz(ctx))


@pass_context
def ha_display(ctx: Context, value: Any) -> Any:
    """Render an aware datetime as a ``<time>`` element; pass everything else through.

    The ``datetime`` attribute carries the UTC instant (machine-readable and
    diff-stable); the element text is the value localised to the resolved
    timezone and formatted with the ``hyperadmin_datetime_format`` Jinja
    global :func:`register_template_filters` registers (``Admin``'s
    ``settings.datetime_format``). Naive datetimes and every other value
    pass through unchanged.

    Enum members render as their label (:func:`get_enum_label`), never as
    ``ContactType.CUSTOMER``; a list, tuple or set of members (a
    ``list[Enum]`` multi-select column) renders as comma-separated labels.
    """
    if isinstance(value, Enum):
        return get_enum_label(value)
    if (
        isinstance(value, list | tuple | set | frozenset)
        and value
        and all(isinstance(v, Enum) for v in value)
    ):
        return ", ".join(get_enum_label(v) for v in value)
    if isinstance(value, datetime) and value.tzinfo is not None:
        tz = resolve_tz(ctx)
        fmt = ctx.get(DATETIME_FORMAT_GLOBAL, _DEFAULT_DISPLAY_FORMAT)
        utc_iso = value.astimezone(dt_timezone.utc).isoformat()
        local_text = to_display(value, tz, fmt)
        return Markup('<time datetime="{}">{}</time>').format(utc_iso, local_text)
    return value


def is_ha_decimal(value: Any) -> bool:
    """Jinja test ``ha_decimal``: True for a ``float`` or ``Decimal`` (never a ``bool``).

    List tables use it to right-align a column and format it with :func:`ha_number`.
    """
    return isinstance(value, float | Decimal)


_MAX_FRACTION_DIGITS = 6


def _resolve_locale(ctx: Context) -> Locale:
    """Return the request locale (``request.state.locale``), ``en`` when unknown."""
    code = getattr(getattr(ctx.get("request"), "state", None), "locale", None) or "en"
    try:
        return Locale.parse(str(code), sep="_")
    except (UnknownLocaleError, ValueError):
        return Locale("en")


@pass_context
def ha_number(ctx: Context, value: Any, currency: str | None = None) -> Any:
    """Format a ``float`` or ``Decimal`` with locale grouping and at least two decimals.

    ``3013.3`` reads ``3,013.30`` in ``en`` and ``3.013,30`` in ``de``. A value
    with more precision keeps it (up to six places). Pass an ISO 4217 ``currency``
    code to format as money (``$3,013.30``). Anything that is not a float or
    Decimal, and a non-finite number, passes through unchanged.
    """
    if not is_ha_decimal(value):
        return value
    # Round float noise (450842.68000000005) away before measuring the precision.
    number = Decimal(str(round(value, _MAX_FRACTION_DIGITS) if isinstance(value, float) else value))
    if not number.is_finite():
        return value
    locale = _resolve_locale(ctx)
    places = min(max(2, -int(number.normalize().as_tuple().exponent)), _MAX_FRACTION_DIGITS)  # type: ignore[call-overload]  # exponent is an int once is_finite()
    if currency:
        return format_currency(number, currency, locale=locale)
    return format_decimal(number, format="#,##0." + "0" * places, locale=locale)


#: Pill tone by lower-cased enum member name, for enums that declare no ``__ha_tones__``.
_DEFAULT_PILL_TONES: dict[str, str] = {
    "paid": "success",
    "active": "success",
    "done": "success",
    "complete": "success",
    "completed": "success",
    "approved": "success",
    "sent": "info",
    "open": "info",
    "in_progress": "info",
    "pending": "warning",
    "on_hold": "warning",
    "overdue": "danger",
    "cancelled": "danger",
    "canceled": "danger",
    "failed": "danger",
    "rejected": "danger",
}


def ha_pill(value: Any, row: Any = None) -> tuple[str, str] | None:
    """Return ``(label, tone)`` for an enum member shown as a status pill, else ``None``.

    The tone comes from the enum class's ``__ha_tones__`` mapping (member name to
    a pill kind such as ``success``, ``warning``, ``danger``, ``info`` or ``""`` for
    neutral), then from a built-in table keyed on the member name. A mapping value may
    also be a callable taking the list ``row``; it returns a tone, or a
    ``(label, tone)`` pair to replace the label as well (an invoice that is Sent
    but past its due date reads "Overdue"). The label is always shown, so colour
    is never the only signal.
    """
    if not isinstance(value, Enum):
        return None
    label = get_enum_label(value)
    tones = getattr(type(value), "__ha_tones__", {})
    tone: Any = tones.get(value.name, _DEFAULT_PILL_TONES.get(value.name.lower(), ""))
    if callable(tone):
        tone = tone(row)
    if isinstance(tone, tuple):
        return str(tone[0]), str(tone[1])
    return label, str(tone)


def register_template_filters(
    env: Environment,
    *,
    default_timezone: tzinfo = dt_timezone.utc,
    datetime_format: str = _DEFAULT_DISPLAY_FORMAT,
) -> None:
    """Register the ``ha_*`` filters on ``env`` and their display defaults.

    ``default_timezone`` becomes the ``hyperadmin_timezone`` Jinja global that
    :func:`resolve_tz` falls back to when a request sets no per-request
    override. ``datetime_format`` becomes the ``hyperadmin_datetime_format``
    Jinja global that :func:`ha_display` formats with. Called once by
    ``HyperAdminRouter`` with ``Admin``'s ``settings.tzinfo`` and
    ``settings.datetime_format``.
    """
    env.globals[TIMEZONE_GLOBAL] = default_timezone
    env.globals[DATETIME_FORMAT_GLOBAL] = datetime_format
    env.filters["ha_pk"] = ha_pk
    env.filters["ha_dom_token"] = ha_dom_token
    env.filters["ha_datetime_input"] = ha_datetime_input
    env.filters["ha_display"] = ha_display
    env.filters["ha_number"] = ha_number
    env.filters["ha_pill"] = ha_pill
    env.tests["ha_decimal"] = is_ha_decimal
    env.globals["ha_timezone_name"] = ha_timezone_name
