"""Unit tests for the chart scale and label arithmetic (``hyperadmin.widgets._scale``)."""

from __future__ import annotations

import pytest

from hyperadmin.widgets._scale import (
    compact_number,
    format_number,
    nice_scale,
    tick_values,
    truncate,
)


@pytest.mark.parametrize(
    ("low", "high", "expected"),
    [
        (30, 71, (0, 80, 20)),  # the design system's revenue chart: €0k … €80k
        (0, 270, (0, 300, 100)),  # stacked totals
        (0, 0, (0, 1, 0.25)),  # all-zero series still gets a drawable axis
        (-35, 60, (-50, 75, 25)),  # negatives keep zero inside the domain
        (5, 9, (0, 10, 2.5)),
    ],
)
def test_nice_scale_rounds_outward_and_includes_zero(low, high, expected) -> None:
    """
    Scenario: the y domain is rounded to readable steps that include the zero baseline.

      Given a data range
      When  nice_scale computes the axis
      Then  start, stop and step are round numbers covering the range and zero
    """
    assert nice_scale(low, high) == pytest.approx(expected)


def test_tick_values_have_no_float_drift() -> None:
    """Ticks of a 0.1 step print as 0.3, not 0.30000000000000004."""
    assert tick_values(0, 0.4, 0.1) == [0.0, 0.1, 0.2, 0.3, 0.4]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1200, "1,200"), (42.0, "42"), (3.14159, "3.14"), (2.5, "2.5"), (-7, "-7")],
)
def test_format_number(value, expected) -> None:
    """Values print with thousands separators and no trailing zeros."""
    assert format_number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(2_500_000_000, "2.5B"), (1_200_000, "1.2M"), (45_000, "45k"), (-3000, "-3k"), (80, "80")],
)
def test_compact_number(value, expected) -> None:
    """Axis ticks are compact so they fit the 44px gutter."""
    assert compact_number(value) == expected


def test_truncate_keeps_short_labels() -> None:
    assert truncate("Q1", 18) == "Q1"


def test_truncate_shortens_long_labels_with_ellipsis() -> None:
    """
    Scenario: long category label is truncated with ellipsis.

      Given a category label longer than the room it has
      When  it is truncated to 18 characters
      Then  it is 18 characters long and ends with "…"
    """
    out = truncate("supercalifragilisticexpialidocious", 18)
    assert out.endswith("…")
    assert len(out) == 18


def test_truncate_to_one_character_still_shows_a_glyph() -> None:
    assert truncate("abc", 1) == "a…"
