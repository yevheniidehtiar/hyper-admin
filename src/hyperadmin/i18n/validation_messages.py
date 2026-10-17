"""Translate pydantic validation errors through the active gettext catalog.

Pydantic builds its error ``msg`` in English, with the constraint values
already interpolated (``"Input should be greater than 5"``). Such a string
cannot be a stable msgid, so :func:`translate_error` maps the error ``type``
to a msgid with ``%(name)s`` placeholders, translates it with the request's
catalog, then fills the placeholders from the error ``ctx``.

The English msgids reproduce pydantic's own wording, so with no catalog (or
the ``en`` catalog) the output is identical to ``err["msg"]``.

Error types that are not mapped fall back to ``gettext(err["msg"])``.

The msgids are marked with :func:`gettext_noop` / :func:`ngettext_noop` so
``poe i18n:extract`` collects them into ``messages.pot``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import babel.support

from hyperadmin.i18n.loader import gettext, ngettext

if TYPE_CHECKING:
    from collections.abc import Mapping


def gettext_noop(message: str) -> str:
    """Mark ``message`` for extraction without translating it."""
    return message


def ngettext_noop(singular: str, plural: str) -> tuple[str, str]:
    """Mark a singular/plural msgid pair for extraction without translating it."""
    return singular, plural


# A plural entry: the msgid pair plus the ``ctx`` key that holds the count.
_Plural = tuple[tuple[str, str], str]

_MESSAGES: dict[str, str] = {
    "missing": gettext_noop("Field required"),
    "string_type": gettext_noop("Input should be a valid string"),
    "string_pattern_mismatch": gettext_noop("String should match pattern '%(pattern)s'"),
    "greater_than": gettext_noop("Input should be greater than %(gt)s"),
    "greater_than_equal": gettext_noop("Input should be greater than or equal to %(ge)s"),
    "less_than": gettext_noop("Input should be less than %(lt)s"),
    "less_than_equal": gettext_noop("Input should be less than or equal to %(le)s"),
    "multiple_of": gettext_noop("Input should be a multiple of %(multiple_of)s"),
    "int_type": gettext_noop("Input should be a valid integer"),
    "int_parsing": gettext_noop(
        "Input should be a valid integer, unable to parse string as an integer"
    ),
    "int_from_float": gettext_noop(
        "Input should be a valid integer, got a number with a fractional part"
    ),
    "float_type": gettext_noop("Input should be a valid number"),
    "float_parsing": gettext_noop(
        "Input should be a valid number, unable to parse string as a number"
    ),
    "bool_type": gettext_noop("Input should be a valid boolean"),
    "bool_parsing": gettext_noop("Input should be a valid boolean, unable to interpret input"),
    "decimal_parsing": gettext_noop("Input should be a valid decimal"),
    "date_parsing": gettext_noop(
        "Input should be a valid date in the format YYYY-MM-DD, %(error)s"
    ),
    "date_from_datetime_parsing": gettext_noop(
        "Input should be a valid date or datetime, %(error)s"
    ),
    "datetime_parsing": gettext_noop("Input should be a valid datetime, %(error)s"),
    "datetime_from_date_parsing": gettext_noop(
        "Input should be a valid datetime or date, %(error)s"
    ),
    "time_parsing": gettext_noop("Input should be in a valid time format, %(error)s"),
    "uuid_parsing": gettext_noop("Input should be a valid UUID, %(error)s"),
    "enum": gettext_noop("Input should be %(expected)s"),
    "literal_error": gettext_noop("Input should be %(expected)s"),
    "url_parsing": gettext_noop("Input should be a valid URL, %(error)s"),
    "json_invalid": gettext_noop("Invalid JSON: %(error)s"),
    "value_error": gettext_noop("Value error, %(error)s"),
    "assertion_error": gettext_noop("Assertion failed, %(error)s"),
}

_PLURAL_MESSAGES: dict[str, _Plural] = {
    "string_too_short": (
        ngettext_noop(
            "String should have at least %(min_length)s character",
            "String should have at least %(min_length)s characters",
        ),
        "min_length",
    ),
    "string_too_long": (
        ngettext_noop(
            "String should have at most %(max_length)s character",
            "String should have at most %(max_length)s characters",
        ),
        "max_length",
    ),
    "too_short": (
        ngettext_noop(
            "%(field_type)s should have at least %(min_length)s item after validation, not %(actual_length)s",
            "%(field_type)s should have at least %(min_length)s items after validation, not %(actual_length)s",
        ),
        "min_length",
    ),
    "too_long": (
        ngettext_noop(
            "%(field_type)s should have at most %(max_length)s item after validation, not %(actual_length)s",
            "%(field_type)s should have at most %(max_length)s items after validation, not %(actual_length)s",
        ),
        "max_length",
    ),
}

# Pydantic omits the actual length of a too-long lazy iterable ("not more").
_TOO_LONG_UNKNOWN_LENGTH: tuple[str, str] = ngettext_noop(
    "%(field_type)s should have at most %(max_length)s item after validation, not more",
    "%(field_type)s should have at most %(max_length)s items after validation, not more",
)

# ``field_type`` values pydantic puts in ``too_short`` / ``too_long`` ctx.
_FIELD_TYPES: tuple[str, ...] = (
    gettext_noop("List"),
    gettext_noop("Tuple"),
    gettext_noop("Set"),
    gettext_noop("Frozenset"),
    gettext_noop("Dictionary"),
)

# ctx keys whose value is itself a human-readable message.
_TRANSLATED_CTX_KEYS: frozenset[str] = frozenset({"error", "field_type"})


def _format_ctx_value(value: Any) -> Any:
    """Render ``value`` the way pydantic-core does in its English message.

    Rust prints whole floats without a fractional part (``5.0`` -> ``5``).
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _translate_text(text: str) -> str:
    """``gettext`` that leaves ``""`` alone (gettext("") returns the catalog header)."""
    return gettext(text) if text else text


def _build_params(ctx: Mapping[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key, value in ctx.items():
        if key in _TRANSLATED_CTX_KEYS:
            params[key] = _translate_text(str(value))
        else:
            params[key] = _format_ctx_value(value)
    return params


def _resolve_template(err_type: str, ctx: Mapping[str, Any]) -> str | None:
    """Return the translated (not yet interpolated) template, or None if unmapped."""
    if err_type in _MESSAGES:
        return gettext(_MESSAGES[err_type])
    if err_type in _PLURAL_MESSAGES:
        (singular, plural), count_key = _PLURAL_MESSAGES[err_type]
        if err_type == "too_long" and ctx.get("actual_length") is None:
            singular, plural = _TOO_LONG_UNKNOWN_LENGTH
        return ngettext(singular, plural, int(ctx[count_key]))
    return None


def translate_error(err: Mapping[str, Any]) -> str:
    """Return the message of pydantic error ``err`` in the active locale.

    ``err`` is one item of ``ValidationError.errors()``. Unknown error types,
    and errors whose ``ctx`` does not fit the mapped template, fall back to
    ``gettext(err["msg"])``.
    """
    msg = str(err["msg"])
    ctx: Mapping[str, Any] = err.get("ctx") or {}
    try:
        template = _resolve_template(str(err.get("type", "")), ctx)
        if template is None:
            return _translate_text(msg)
        return template % _build_params(ctx)
    except (KeyError, TypeError, ValueError):
        return _translate_text(msg)


def translate_error_lazy(err: Mapping[str, Any]) -> babel.support.LazyProxy:
    """Lazy variant of :func:`translate_error`, re-translated on every ``str()``.

    Form errors are rendered after validation and may be re-rendered under a
    different locale, so they keep the error and translate at render time.
    """
    return babel.support.LazyProxy(lambda: translate_error(err), enable_cache=False)


__all__ = [
    "gettext_noop",
    "ngettext_noop",
    "translate_error",
    "translate_error_lazy",
]
