"""Unit tests for ``hyperadmin.core.timezones`` and ``settings.timezone``."""

from __future__ import annotations

import functools
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.core.timezones import (
    format_datetime_input,
    is_auto_now_factory,
    parse_datetime_input,
    to_display,
    utc_now,
)

AMS = ZoneInfo("Europe/Amsterdam")
UTC = timezone.utc


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-14)
# ---------------------------------------------------------------------------


def test_naive_input_is_localised_for_aware_columns() -> None:
    """
    Scenario: naive input is localised for aware columns
      Given tz Europe/Amsterdam and kind aware
      When  parse_datetime_input('2026-07-01T10:00') runs
      Then  2026-07-01T08:00Z is returned
    """
    result = parse_datetime_input("2026-07-01T10:00", kind="aware", tz=AMS)

    assert result == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    assert result.utcoffset() == timedelta(0)


def test_naive_columns_keep_wall_clock_time() -> None:
    """
    Scenario: naive columns keep wall-clock time
      Given kind naive
      When  parse_datetime_input('2026-07-01T10:00') runs
      Then  a naive 10:00 datetime is returned
    """
    result = parse_datetime_input("2026-07-01T10:00", kind="naive", tz=AMS)

    assert result == datetime(2026, 7, 1, 10, 0)
    assert result.tzinfo is None


def test_aware_values_format_in_the_display_timezone() -> None:
    """
    Scenario: aware values format in the display timezone
      Given an aware 08:00Z value and tz Europe/Amsterdam
      When  format_datetime_input runs
      Then  '2026-07-01T10:00:00' is returned
    """
    value = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)

    assert format_datetime_input(value, AMS) == "2026-07-01T10:00:00"


def test_tz_aware_lambda_is_auto_now() -> None:
    """
    Scenario: tz-aware lambda is auto-now
      Given lambda: datetime.now(timezone.utc)
      When  is_auto_now_factory runs
      Then  True is returned
    """
    assert is_auto_now_factory(lambda: datetime.now(timezone.utc)) is True


def test_invalid_timezone_setting_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: invalid timezone setting is rejected
      Given HYPERADMIN_TIMEZONE=Mars/Olympus
      When  settings load
      Then  a validation error is raised
    """
    monkeypatch.setenv("HYPERADMIN_TIMEZONE", "Mars/Olympus")

    with pytest.raises(ValidationError, match="timezone"):
        HyperAdminSettings()


def test_dst_gap_is_deterministic() -> None:
    """
    Scenario: DST gap is deterministic
      Given the Europe/Amsterdam spring-forward gap
      When  02:30 is parsed
      Then  the fold=0 result is returned
    """
    result = parse_datetime_input("2026-03-29T02:30", kind="aware", tz=AMS)

    # fold=0 in the gap uses the pre-transition offset (+01:00).
    assert result == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    assert parse_datetime_input("2026-03-29T02:30", kind="aware", tz=AMS) == result


# ---------------------------------------------------------------------------
# utc_now / is_auto_now_factory
# ---------------------------------------------------------------------------


def test_utc_now_is_aware_utc() -> None:
    value = utc_now()

    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "factory",
    [
        datetime.now,
        datetime.utcnow,
        utc_now,
        functools.partial(datetime.now, UTC),
        lambda: datetime.utcnow(),  # noqa: PLW0108 — the lambda wrapper is the case under test
    ],
)
def test_known_now_factories_are_auto_now(factory: object) -> None:
    assert is_auto_now_factory(factory) is True


def test_marked_factory_is_auto_now() -> None:
    def stamp() -> datetime:
        return datetime(2020, 1, 1)

    stamp.__hyperadmin_auto_now__ = True  # type: ignore[attr-defined]

    assert is_auto_now_factory(stamp) is True


def test_named_function_is_not_auto_now() -> None:
    """A named factory is the documented escape hatch from auto-now detection."""

    def my_default() -> datetime:
        return datetime.now(UTC)

    assert is_auto_now_factory(my_default) is False


@pytest.mark.parametrize("factory", [None, list, dict, lambda: 0, "now"])
def test_other_factories_are_not_auto_now(factory: object) -> None:
    assert is_auto_now_factory(factory) is False


# ---------------------------------------------------------------------------
# parse_datetime_input
# ---------------------------------------------------------------------------


def test_aware_input_with_offset_is_respected() -> None:
    result = parse_datetime_input("2026-07-01T10:00+05:00", kind="aware", tz=AMS)

    assert result == datetime(2026, 7, 1, 5, 0, tzinfo=UTC)


def test_aware_input_with_z_suffix() -> None:
    result = parse_datetime_input("2026-07-01T10:00:00Z", kind="aware", tz=AMS)

    assert result == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)


def test_naive_column_with_offset_input_converts_to_display_tz() -> None:
    result = parse_datetime_input("2026-07-01T08:00+00:00", kind="naive", tz=AMS)

    assert result == datetime(2026, 7, 1, 10, 0)
    assert result.tzinfo is None


def test_parse_strips_whitespace_and_keeps_seconds() -> None:
    result = parse_datetime_input(" 2026-07-01T10:00:05 ", kind="naive", tz=UTC)

    assert result == datetime(2026, 7, 1, 10, 0, 5)


@pytest.mark.parametrize("raw", ["", "yesterday", "2026-13-01T00:00"])
def test_parse_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 — message comes from stdlib fromisoformat
        parse_datetime_input(raw, kind="naive", tz=UTC)


# ---------------------------------------------------------------------------
# format_datetime_input / to_display
# ---------------------------------------------------------------------------


def test_format_naive_value_is_unchanged() -> None:
    assert format_datetime_input(datetime(2026, 7, 1, 10, 0, 0, 123), AMS) == (
        "2026-07-01T10:00:00"
    )


def test_format_none_is_empty() -> None:
    assert format_datetime_input(None, AMS) == ""


def test_format_passes_strings_through() -> None:
    assert format_datetime_input("2026-07-01T10:00", AMS) == "2026-07-01T10:00"


def test_format_date_value() -> None:
    assert format_datetime_input(date(2026, 7, 1), AMS) == "2026-07-01"


def test_to_display_converts_aware_values() -> None:
    value = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)

    assert to_display(value, AMS, "%Y-%m-%d %H:%M") == "2026-07-01 10:00"


def test_to_display_leaves_naive_values_alone() -> None:
    value = datetime(2026, 7, 1, 8, 0)

    assert to_display(value, AMS, "%Y-%m-%d %H:%M") == "2026-07-01 08:00"


# ---------------------------------------------------------------------------
# settings.timezone
# ---------------------------------------------------------------------------


def test_timezone_setting_defaults_to_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HYPERADMIN_TIMEZONE", raising=False)

    settings = HyperAdminSettings()

    assert settings.timezone == "UTC"
    assert settings.tzinfo == ZoneInfo("UTC")


def test_timezone_setting_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HYPERADMIN_TIMEZONE", "Europe/Amsterdam")

    settings = HyperAdminSettings()

    assert settings.timezone == "Europe/Amsterdam"
    assert settings.tzinfo == AMS


@pytest.mark.parametrize("value", ["", "../etc/passwd", "Not/AZone"])
def test_timezone_setting_rejects_bad_keys(value: str) -> None:
    with pytest.raises(ValidationError):
        HyperAdminSettings(timezone=value)


@pytest.mark.parametrize("value", ["utc", "europe/amsterdam", "EUROPE/AMSTERDAM"])
def test_timezone_setting_rejects_non_canonical_case(value: str) -> None:
    """
    Scenario: a wrongly-cased zone fails on every host
      Given HYPERADMIN_TIMEZONE spelled with the wrong case
      When  settings load (even on a case-insensitive filesystem)
      Then  a validation error naming the canonical spelling is raised
    """
    with pytest.raises(ValidationError, match="timezone"):
        HyperAdminSettings(timezone=value)


# ---------------------------------------------------------------------------
# Out-of-range input (review of st-v058-byoa-14)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "kind", "tz"),
    [
        ("0001-01-01T00:00", "aware", AMS),
        ("9999-12-31T23:00", "aware", ZoneInfo("America/New_York")),
        ("9999-12-31T23:00:00-05:00", "aware", UTC),
        ("0001-01-01T00:00:00+05:00", "naive", UTC),
        ("9999-12-31T23:00:00-05:00", "naive", AMS),
    ],
)
def test_out_of_range_input_raises_value_error(raw: str, kind: str, tz: ZoneInfo) -> None:
    """
    Scenario: a datetime that overflows on conversion is invalid input
      Given a value at the edge of the supported date range
      When  parse_datetime_input converts it between zones
      Then  ValueError (not OverflowError) is raised
    """
    with pytest.raises(ValueError, match="range"):
        parse_datetime_input(raw, kind=kind, tz=tz)  # type: ignore[arg-type]


def test_utc_now_is_exported_from_core() -> None:
    from hyperadmin import core

    assert core.utc_now is utc_now
    assert "utc_now" in core.__all__
