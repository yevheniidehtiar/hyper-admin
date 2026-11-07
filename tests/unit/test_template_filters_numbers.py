"""Unit tests for the ``ha_number`` filter, ``ha_decimal`` test and ``ha_pill`` filter.

Covers st-ux-erp-04 (money formatting) and st-ux-erp-13 (status pills).
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from types import SimpleNamespace

from jinja2 import Environment

from hyperadmin.views.template_filters import ha_pill, register_template_filters


def _env() -> Environment:
    env = Environment()
    register_template_filters(env)
    return env


def _number(value: object, *, locale: object = "en", currency: str | None = None) -> str:
    request = SimpleNamespace(state=SimpleNamespace(hyperadmin_timezone=None, locale=locale))
    return (
        _env()
        .from_string("{{ value|ha_number(currency) }}")
        .render(request=request, value=value, currency=currency)
    )


def test_ha_number_groups_and_pads_to_two_decimals() -> None:
    """
    Scenario: amounts are formatted
      Given a float 3013.3 and a Decimal 1048282.18 in locale en
      When  ha_number runs
      Then  they read 3,013.30 and 1,048,282.18
    """
    assert _number(3013.3) == "3,013.30"
    assert _number(Decimal("1048282.18")) == "1,048,282.18"
    assert _number(0.0) == "0.00"


def test_ha_number_keeps_extra_precision_up_to_six_places() -> None:
    """A value with more than two decimals keeps them, capped at six."""
    assert _number(Decimal("1.23456")) == "1.23456"
    assert _number(Decimal("1.123456789")) == "1.123457"


def test_ha_number_drops_float_noise_and_trailing_zeros() -> None:
    """Float noise and a padded Decimal scale do not show as extra decimals."""
    assert _number(450842.68000000005) == "450,842.68"
    assert _number(Decimal("1.230000")) == "1.23"
    assert _number(Decimal("1E+3")) == "1,000.00"


def test_ha_number_follows_the_request_locale() -> None:
    """The separators come from ``request.state.locale``; unknown locales fall back to en."""
    assert _number(3013.3, locale="de") == "3.013,30"
    assert _number(3013.3, locale="xx_not_a_locale") == "3,013.30"
    assert _number(3013.3, locale=None) == "3,013.30"


def test_ha_number_formats_money_with_a_currency_code() -> None:
    """An ISO 4217 code formats the value as money."""
    assert _number(3013.3, currency="EUR") == "€3,013.30"


def test_ha_number_passes_other_values_through() -> None:
    """Ints, bools, strings and non-finite numbers are left alone."""
    assert _number(7) == "7"
    assert _number(True) == "True"
    assert _number("abc") == "abc"
    assert _number(float("nan")) == "nan"


def test_ha_decimal_test_matches_float_and_decimal_only() -> None:
    """The ``ha_decimal`` test is True for float/Decimal, never for int or bool."""
    tmpl = _env().from_string("{{ v is ha_decimal }}")
    assert tmpl.render(v=1.5) == "True"
    assert tmpl.render(v=Decimal(1)) == "True"
    assert tmpl.render(v=1) == "False"
    assert tmpl.render(v=True) == "False"


class _Tone(Enum):
    PAID = "Paid"
    SENT = "Sent"
    LATE = "Late"
    NAMED = "Named"

    __ha_tones__ = {
        "SENT": lambda row: ("Overdue", "danger") if row and row.get("late") else "info",
        "LATE": lambda row: "warning",
        "NAMED": "info",
    }


class _Plain(Enum):
    PAID = "Paid"
    CANCELLED = "Cancelled"
    OTHER = "Other"


def test_ha_pill_uses_declared_and_default_tones() -> None:
    """
    Scenario: status is shown as a pill
      Given an enum member Paid
      When  ha_pill runs
      Then  the label is "Paid" with the success tone
    """
    assert ha_pill(_Plain.PAID) == ("Paid", "success")
    assert ha_pill(_Plain.CANCELLED) == ("Cancelled", "danger")
    assert ha_pill(_Plain.OTHER) == ("Other", "")
    assert ha_pill(_Tone.NAMED) == ("Named", "info")
    assert ha_pill(_Tone.PAID) == ("Paid", "success")


def test_ha_pill_lets_a_row_callable_pick_the_tone_and_label() -> None:
    """A tone callable sees the row and may replace the label (overdue variant)."""
    assert ha_pill(_Tone.SENT, {"late": True}) == ("Overdue", "danger")
    assert ha_pill(_Tone.SENT, {"late": False}) == ("Sent", "info")
    assert ha_pill(_Tone.SENT) == ("Sent", "info")
    assert ha_pill(_Tone.LATE, {}) == ("Late", "warning")


def test_ha_pill_ignores_non_enum_values() -> None:
    """Strings, numbers and None are not pills."""
    assert ha_pill("Paid") is None
    assert ha_pill(None) is None
