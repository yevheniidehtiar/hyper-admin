"""Unit tests for the ``hyperadmin.filters`` package and ``core/filters_compat``.

Covers the story scenarios of st-v056-fl-01 (``docs/specs/filter-library.md``):

  Scenario: legacy list_filter=["status"] is wrapped into a FilterDef
  Scenario: DateRangeFilter.parse extracts gte/lte from querystring
  Scenario: IsOwnerFilter with anonymous user applies nothing

plus per-filter parse / compile / describe / render behaviour.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from jinja2 import Environment, FileSystemLoader
from pydantic import AwareDatetime, BaseModel
from starlette.datastructures import QueryParams

from hyperadmin.core.filtering import MAX_IN_VALUES, FilterCondition
from hyperadmin.core.filters_compat import LegacyFieldFilter, collect_filters
from hyperadmin.filters import (
    PRESETS,
    BooleanFilter,
    CurrentPeriodDefault,
    DateRangeFilter,
    FilterBinding,
    FilterDef,
    FilterRenderContext,
    IsOwnerFilter,
    MultiChoiceFilter,
    MultiFKFilter,
    period_bounds,
)
from hyperadmin.filters.base import (
    _TEMPLATES_DIR,
    clear_href,
    default_environment,
    is_truthy,
    query_pairs,
    query_value,
    query_values,
)
from hyperadmin.filters.date import FROM_AFTER_TO, INVALID_DATE

TODAY = date(2026, 10, 20)
AMS = ZoneInfo("Europe/Amsterdam")


class Status(enum.Enum):
    DRAFT = "draft"
    DONE = "done"


class Order(BaseModel):
    created_at: datetime | None = None
    paid_at: AwareDatetime | None = None
    shipped_on: date | None = None
    is_paid: bool = True
    status: Status = Status.DRAFT
    supplier_id: int | None = None
    created_by: int = 0
    assigned_to: int = 0


def _binding(**kwargs: Any) -> FilterBinding:
    return FilterBinding(model=Order, today=TODAY, **kwargs)


def _choices(*pairs: tuple[str, str]) -> list[Any]:
    return [{"value": value, "label": label, "selected": False} for value, label in pairs]


# ---------------------------------------------------------------------------
# Querystring helpers
# ---------------------------------------------------------------------------


def test_query_values_reads_query_params_mappings_and_none() -> None:
    params = QueryParams([("a", "1"), ("a", " 2 "), ("a", "")])

    assert query_values(params, "a") == ["1", "2"]
    assert query_values({"a": ["x", "", "y"]}, "a") == ["x", "y"]
    assert query_values({"a": "z"}, "a") == ["z"]
    assert query_values({"a": None}, "a") == []
    assert query_values(None, "a") == []
    assert query_values(object(), "a") == []


def test_query_value_returns_last_or_none() -> None:
    assert query_value(QueryParams([("a", "1"), ("a", "2")]), "a") == "2"
    assert query_value({}, "a") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("TRUE", True), (" yes ", True), ("on", True), ("0", False), (None, False)],
)
def test_is_truthy(raw: str | None, expected: bool) -> None:
    assert is_truthy(raw) is expected


def test_query_pairs_flattens_every_input_shape() -> None:
    assert query_pairs(QueryParams([("a", "1"), ("a", "2")])) == [("a", "1"), ("a", "2")]
    assert query_pairs({"a": ["1", "2"], "b": "3", "c": None}) == [
        ("a", "1"),
        ("a", "2"),
        ("b", "3"),
    ]
    assert query_pairs(None) == []
    assert query_pairs(object()) == []


def test_clear_href_drops_keys_and_page_and_appends_extra() -> None:
    qs = QueryParams([("search", "x"), ("page", "3"), ("f__gte", "2026-01-01")])

    assert clear_href(qs, ("f__gte",)) == "?search=x"
    assert clear_href(qs, ("f__gte",), {"f": "all"}) == "?search=x&f=all"
    assert clear_href(None, ()) == "?"


# ---------------------------------------------------------------------------
# FilterBinding / FilterRenderContext / FilterDef base
# ---------------------------------------------------------------------------


def test_binding_today_defaults_to_now_in_tz() -> None:
    binding = FilterBinding(tz=AMS)

    assert binding.today_date == datetime.now(AMS).date()
    assert FilterBinding(today=TODAY).today_date == TODAY


def test_filter_def_defaults_title_slug_and_query_keys() -> None:
    f = BooleanFilter(field="is_paid")

    assert f.title == "Is Paid"
    assert f.slug == "is_paid"
    assert f.query_keys == ("is_paid",)
    assert BooleanFilter(field="is_paid", label="Paid").title == "Paid"
    assert isinstance(f, FilterDef)
    assert f.error({}) is None


def test_filter_def_hooks_default_to_inactive() -> None:
    """A minimal subclass gets ``error``/``describe`` hooks that report nothing."""

    class Exact(FilterDef):
        template = "components/filters/select.html"

        def parse(self, qs: Any) -> dict[str, Any]:
            raw = query_value(qs, self.field)
            return {"value": raw} if raw else {}

        def compile(
            self, parsed: dict[str, Any], binding: FilterBinding | None = None
        ) -> list[FilterCondition]:
            return self.typed_conditions(binding, {"": parsed["value"]}) if parsed else []

    f = Exact(field="status")

    assert f.describe(f.parse({"status": "done"})) is None
    assert f.error({"status": "done"}) is None
    assert f.compile(f.parse({"status": "done"}), _binding()) == [
        FilterCondition("status", "exact", Status.DONE)
    ]


def test_filter_def_is_immutable() -> None:
    f = BooleanFilter(field="is_paid")

    with pytest.raises(AttributeError):
        f.field = "other"  # type: ignore[misc]


def test_typed_conditions_fall_back_to_value_type_without_model() -> None:
    """Unbound filters still coerce: a DateRangeFilter emits dates, not strings."""
    f = DateRangeFilter(field="created_at")

    conditions = f.compile(f.parse({"created_at__gte": "2026-01-01"}))

    assert conditions == [FilterCondition("created_at", "gte", date(2026, 1, 1))]


def test_typed_conditions_use_the_model_annotation_when_bound() -> None:
    """Scenario: a whole day on an aware column is a local day in the display timezone."""
    f = DateRangeFilter(field="paid_at")
    binding = _binding(tz=AMS, datetime_kind=lambda _name: "aware")

    conditions = f.compile(f.parse({"paid_at__lte": "2026-01-31"}), binding)

    assert conditions == [
        FilterCondition(
            "paid_at", "lte", datetime(2026, 1, 31, 22, 59, 59, 999999, tzinfo=timezone.utc)
        )
    ]


def test_render_uses_the_default_environment_and_a_custom_one() -> None:
    f = BooleanFilter(field="is_paid")
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
    env.add_extension("jinja2.ext.i18n")
    env.install_null_translations(newstyle=True)  # type: ignore[attr-defined]

    html = f.render(FilterRenderContext(query={"is_paid": "1"}))
    custom = f.render(FilterRenderContext(query={"is_paid": "1"}, templates=env))

    assert 'data-testid="filter-is_paid"' in html
    assert 'value="1" checked' in html
    assert custom == html
    assert default_environment() is default_environment()


# ---------------------------------------------------------------------------
# DateRangeFilter
# ---------------------------------------------------------------------------


def test_date_range_parse_extracts_gte_lte() -> None:
    """
    Scenario: DateRangeFilter.parse extracts gte/lte from querystring
      Given DateRangeFilter(field="created_at")
      When  parse({"created_at__gte": "2026-01-01", "created_at__lte": "2026-01-31"}) is called
      Then  the result is {"gte": date(2026,1,1), "lte": date(2026,1,31)}
    """
    f = DateRangeFilter(field="created_at")

    parsed = f.parse({"created_at__gte": "2026-01-01", "created_at__lte": "2026-01-31"})

    assert parsed == {"gte": date(2026, 1, 1), "lte": date(2026, 1, 31)}
    assert f.query_keys == ("created_at__gte", "created_at__lte", "created_at__preset")
    assert f.parse({}) == {}
    assert f.parse({"created_at__gte": "2026-01-01"}) == {"gte": date(2026, 1, 1)}


def test_date_range_compile_expands_whole_days_on_datetime_columns() -> None:
    f = DateRangeFilter(field="created_at")

    conditions = f.compile(
        f.parse({"created_at__gte": "2026-01-01", "created_at__lte": "2026-01-31"}), _binding()
    )

    assert conditions == [
        FilterCondition("created_at", "gte", datetime(2026, 1, 1, 0, 0)),
        FilterCondition("created_at", "lte", datetime(2026, 1, 31, 23, 59, 59, 999999)),
    ]
    assert f.compile({}, _binding()) == []


def test_date_range_invalid_input_parses_empty_and_reports_an_error() -> None:
    """Scenario: invalid date input — parse returns {} and the sidebar shows an inline error."""
    f = DateRangeFilter(field="created_at")
    bad = {"created_at__gte": "not-a-date"}
    swapped = {"created_at__gte": "2026-02-01", "created_at__lte": "2026-01-31"}

    assert f.parse(bad) == {}
    assert f.error(bad) == INVALID_DATE
    assert f.parse(swapped) == {}
    assert f.error(swapped) == FROM_AFTER_TO
    assert f.error({"created_at__gte": "2026-01-01"}) is None

    html = f.render(FilterRenderContext(query=swapped, binding=_binding()))

    assert 'data-testid="filter-created_at-error"' in html
    assert FROM_AFTER_TO in html
    assert 'aria-invalid="true"' in html
    assert 'value="2026-02-01"' in html  # the bad input is echoed back for correction


def test_date_range_preset_wins_and_resolves_against_today() -> None:
    f = DateRangeFilter(field="created_at")
    qs = {"created_at__preset": "last_month", "created_at__gte": "2026-01-01"}

    parsed = f.parse(qs)

    assert parsed == {"preset": "last_month"}
    assert f.error(qs) is None
    assert f.bounds(parsed, _binding()) == (date(2026, 9, 1), date(2026, 9, 30))
    assert f.describe(parsed) == "last month"
    assert f.compile(parsed, _binding()) == [
        FilterCondition("created_at", "gte", datetime(2026, 9, 1, 0, 0)),
        FilterCondition("created_at", "lte", datetime(2026, 9, 30, 23, 59, 59, 999999)),
    ]


def test_date_range_unknown_preset_is_ignored() -> None:
    f = DateRangeFilter(field="created_at", presets=("today",))

    assert f.parse({"created_at__preset": "this_month"}) == {}
    with pytest.raises(ValueError, match="Unknown presets"):
        DateRangeFilter(field="created_at", presets=("yesterday",))


@pytest.mark.parametrize(
    ("parsed", "expected"),
    [
        ({}, None),
        ({"gte": date(2026, 1, 1), "lte": date(2026, 1, 31)}, "2026-01-01 to 2026-01-31"),
        ({"gte": date(2026, 1, 1)}, "from 2026-01-01"),
        ({"lte": date(2026, 1, 31)}, "until 2026-01-31"),
    ],
)
def test_date_range_describe(parsed: dict[str, Any], expected: str | None) -> None:
    assert DateRangeFilter(field="created_at").describe(parsed) == expected


def test_date_range_renders_inputs_presets_and_clear_link() -> None:
    """
    Scenario: explicit DateRangeFilter renders two date inputs
      Given AdminOptions(list_filter=[DateRangeFilter(field="created_at")])
      When  the sidebar renders
      Then  it exposes inputs created_at__gte and created_at__lte
      And   each input has data-testid="filter-created_at-gte" / "-lte"
    """
    f = DateRangeFilter(field="created_at", label="Created")
    qs = QueryParams([("created_at__preset", "this_month"), ("search", "x")])

    html = f.render(FilterRenderContext(query=qs, binding=_binding()))

    assert 'name="created_at__gte" value="2026-10-01" data-testid="filter-created_at-gte"' in html
    assert 'name="created_at__lte" value="2026-10-31" data-testid="filter-created_at-lte"' in html
    assert 'value="this_month" aria-pressed="true"' in html
    assert 'value="today" aria-pressed="false"' in html
    assert 'href="?search=x"' in html  # Clear drops only this filter's keys
    assert "<legend>Created" in html

    bare = DateRangeFilter(field="created_at", presets=()).render(FilterRenderContext(query={}))

    assert "ha-presets" not in bare
    assert "ha-filtergroup__clear" not in bare


@pytest.mark.parametrize(
    ("period", "today", "offset", "expected"),
    [
        ("day", TODAY, 0, (TODAY, TODAY)),
        ("day", TODAY, -1, (date(2026, 10, 19), date(2026, 10, 19))),
        ("week", TODAY, 0, (date(2026, 10, 19), date(2026, 10, 25))),
        ("week", TODAY, -1, (date(2026, 10, 12), date(2026, 10, 18))),
        ("month", TODAY, 0, (date(2026, 10, 1), date(2026, 10, 31))),
        ("month", date(2026, 1, 15), -1, (date(2025, 12, 1), date(2025, 12, 31))),
        ("month", date(2024, 2, 10), 0, (date(2024, 2, 1), date(2024, 2, 29))),
        ("quarter", date(2026, 12, 5), 0, (date(2026, 10, 1), date(2026, 12, 31))),
        ("quarter", date(2026, 2, 5), -1, (date(2025, 10, 1), date(2025, 12, 31))),
        ("year", TODAY, 0, (date(2026, 1, 1), date(2026, 12, 31))),
        ("year", TODAY, 1, (date(2027, 1, 1), date(2027, 12, 31))),
    ],
)
def test_period_bounds(period: Any, today: date, offset: int, expected: tuple[date, date]) -> None:
    assert period_bounds(period, today, offset) == expected


def test_presets_cover_the_design_buttons() -> None:
    assert list(PRESETS) == ["today", "this_week", "this_month", "last_month", "this_quarter"]


# ---------------------------------------------------------------------------
# CurrentPeriodDefault
# ---------------------------------------------------------------------------


def test_current_period_default_applies_on_first_load() -> None:
    """
    Scenario: CurrentPeriodDefault preselects the current month on first load
      Given CurrentPeriodDefault(field="created_at", period="month") and no querystring
      When  the user opens the list
      Then  the URL is redirected to ?created_at__gte=<first of month>&created_at__lte=<today>
    """
    f = CurrentPeriodDefault(field="created_at", period="month")
    binding = _binding()

    assert f.applies({}) is True
    assert f.parse({}) == {"period": "month"}
    assert f.default_params(binding) == {
        "created_at__gte": "2026-10-01",
        "created_at__lte": "2026-10-20",
    }
    assert (
        f.redirect_query(QueryParams([("page", "2"), ("search", "x")]), binding)
        == "search=x&created_at__gte=2026-10-01&created_at__lte=2026-10-20"
    )
    assert f.compile(f.parse({}), binding) == [
        FilterCondition("created_at", "gte", datetime(2026, 10, 1, 0, 0)),
        FilterCondition("created_at", "lte", datetime(2026, 10, 20, 23, 59, 59, 999999)),
    ]
    assert f.describe(f.parse({})) == "this month"
    assert f.slug == "created_at-default"
    assert f.query_keys == (
        "created_at",
        "created_at__gte",
        "created_at__lte",
        "created_at__preset",
    )


@pytest.mark.parametrize(
    "qs",
    [
        {"created_at__gte": "2026-01-01"},
        {"created_at__lte": "2026-01-31"},
        {"created_at__preset": "today"},
        {"created_at": "all"},
    ],
)
def test_current_period_default_yields_to_user_input(qs: dict[str, str]) -> None:
    """Scenario: CurrentPeriodDefault already overridden by user querystring — default skipped."""
    f = CurrentPeriodDefault(field="created_at")

    assert f.applies(qs) is False
    assert f.parse(qs) == {}
    assert f.redirect_query(qs) is None
    assert f.compile({}, _binding()) == []
    assert f.describe({}) is None
    assert f.render(FilterRenderContext(query=qs)) == ""


def test_current_period_default_renders_the_hint_with_show_all_link() -> None:
    f = CurrentPeriodDefault(field="created_at", period="week")

    html = f.render(FilterRenderContext(query={"search": "x"}, binding=_binding()))

    assert 'data-testid="filter-created_at-default"' in html
    assert "Showing this week by default." in html
    assert 'href="?search=x&amp;created_at=all"' in html
    assert "created_at__gte=2026-10-19&amp;created_at__lte=2026-10-20" in html


def test_current_period_default_rejects_unknown_period() -> None:
    with pytest.raises(ValueError, match="Unknown period"):
        CurrentPeriodDefault(field="created_at", period="fortnight")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MultiFKFilter
# ---------------------------------------------------------------------------


def test_multi_fk_parse_accepts_repeated_and_comma_separated_values() -> None:
    f = MultiFKFilter(field="supplier_id")
    qs = QueryParams([("supplier_id__in", "1"), ("supplier_id__in", "2,3, 1 ,")])

    assert f.parse(qs) == {"in": ["1", "2", "3"]}
    assert f.parse({}) == {}
    assert f.query_keys == ("supplier_id__in",)
    assert f.describe({"in": ["1", "2"]}) == "2 selected"
    assert f.describe({}) is None


def test_multi_fk_caps_the_number_of_values() -> None:
    f = MultiFKFilter(field="supplier_id")
    raw = ",".join(str(i) for i in range(MAX_IN_VALUES + 5))

    assert len(f.parse({"supplier_id__in": raw})["in"]) == MAX_IN_VALUES


def test_multi_fk_compile_coerces_to_the_column_type() -> None:
    f = MultiFKFilter(field="supplier_id")

    assert f.compile(f.parse({"supplier_id__in": "1,2"}), _binding()) == [
        FilterCondition("supplier_id", "in", (1, 2))
    ]
    assert f.compile({}, _binding()) == []


def test_multi_fk_stale_values_are_dropped_silently() -> None:
    """Scenario: MultiFKFilter choice points to a deleted row — a bad value is ignored."""
    f = MultiFKFilter(field="supplier_id")

    assert f.compile(f.parse({"supplier_id__in": "abc"}), _binding()) == []


def test_multi_fk_renders_checklist_selected_first_with_search_and_more() -> None:
    f = MultiFKFilter(field="supplier_id", label="Supplier")
    ctx = FilterRenderContext(
        query={"supplier_id__in": "2"},
        choices=_choices(("1", "Acme"), ("2", "Brabant")),
        more=18,
    )

    html = f.render(ctx)

    assert html.index('value="2" checked>Brabant') < html.index('value="1">Acme')
    assert 'data-testid="filter-supplier_id-search"' in html
    assert 'placeholder="Search supplier"' in html
    assert "1 selected" in html
    assert 'data-testid="filter-supplier_id-more">Show 18 more' in html

    plain = MultiFKFilter(field="supplier_id", searchable=False).render(
        FilterRenderContext(query={}, choices=_choices(("1", "Acme")))
    )

    assert "ha-checklist__search" not in plain
    assert "ha-checklist__more" not in plain


# ---------------------------------------------------------------------------
# MultiChoiceFilter
# ---------------------------------------------------------------------------


def test_multi_choice_from_enum_drops_unknown_values_and_coerces() -> None:
    f = MultiChoiceFilter(field="status", choices=Status)

    assert f.options == [("draft", "Draft"), ("done", "Done")]
    assert f.parse({"status__in": "done,bogus"}) == {"in": ["done"]}
    assert f.parse({"status__in": "bogus"}) == {}
    assert f.compile({"in": ["done"]}, _binding()) == [
        FilterCondition("status", "in", (Status.DONE,))
    ]
    assert f.compile({}, _binding()) == []
    assert f.describe({"in": ["done", "draft"]}) == "Done, Draft"
    assert f.describe({}) is None


def test_multi_choice_from_pairs_and_undeclared() -> None:
    pairs = MultiChoiceFilter(field="status", choices=[("a", "Alpha"), ("b", "Beta")])
    free = MultiChoiceFilter(field="status")

    assert pairs.options == [("a", "Alpha"), ("b", "Beta")]
    assert pairs.parse({"status__in": "b,zzz"}) == {"in": ["b"]}
    assert free.options == []
    assert free.parse({"status__in": "anything"}) == {"in": ["anything"]}
    assert free.describe({"in": ["anything"]}) == "anything"


def test_multi_choice_renders_declared_or_context_choices() -> None:
    declared = MultiChoiceFilter(field="status", choices=Status, label="Status")
    free = MultiChoiceFilter(field="status")

    html = declared.render(FilterRenderContext(query={"status__in": "done"}))
    ctx_html = free.render(FilterRenderContext(query={}, choices=_choices(("x", "Ex"))))

    assert 'name="status__in" value="done" checked>Done' in html
    assert 'name="status__in" value="draft">Draft' in html
    assert "ha-filtergroup__clear" in html
    assert 'value="x">Ex' in ctx_html


# ---------------------------------------------------------------------------
# BooleanFilter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "parsed", "conditions", "chip", "state"),
    [
        ("1", {"value": True}, [FilterCondition("is_paid", "exact", True)], "Yes", "1"),
        ("no", {"value": False}, [FilterCondition("is_paid", "exact", False)], "No", "0"),
        ("", {}, [], None, ""),
        ("maybe", {}, [], None, ""),
    ],
)
def test_boolean_filter_tri_state(
    raw: str, parsed: dict[str, Any], conditions: list[Any], chip: str | None, state: str
) -> None:
    f = BooleanFilter(field="is_paid")
    qs = {"is_paid": raw}

    assert f.parse(qs) == parsed
    assert f.compile(parsed, _binding()) == conditions
    assert f.describe(parsed) == chip
    assert f.context(FilterRenderContext(query=qs))["state"] == state


def test_boolean_filter_renders_real_radios() -> None:
    html = BooleanFilter(field="is_paid", label="Paid").render(FilterRenderContext(query={}))

    assert 'role="radiogroup"' in html
    assert 'name="is_paid" value="" checked' in html
    assert html.count('type="radio"') == 3


# ---------------------------------------------------------------------------
# IsOwnerFilter
# ---------------------------------------------------------------------------


def test_is_owner_filter_anonymous_user_applies_nothing() -> None:
    """
    Scenario: IsOwnerFilter with anonymous user applies nothing
      Given IsOwnerFilter(owner_fields="created_by") and no user
      When  compile(parsed={"is_owner": True}) is called
      Then  no condition is produced
    """
    f = IsOwnerFilter(owner_fields="created_by")

    assert f.compile({"is_owner": True}) == []
    assert f.compile({"is_owner": True}, FilterBinding(user=object(), user_key=None)) == []
    assert f.compile({}, FilterBinding(user_key=7)) == []


def test_is_owner_filter_single_field_compiles_to_exact() -> None:
    """
    Scenario: IsOwnerFilter restricts to objects the user owns
      Given IsOwnerFilter(owner_fields="created_by") and the user is alice
      When  the user toggles "Mine only" (?is_owner=1)
      Then  the result rows all have created_by == alice's user key
    """
    f = IsOwnerFilter(owner_fields="created_by")

    assert f.field == "created_by"
    assert f.slug == "is_owner"
    assert f.query_keys == ("is_owner",)
    assert f.parse({"is_owner": "1"}) == {"is_owner": True}
    assert f.parse({"is_owner": "0"}) == {}
    assert f.compile({"is_owner": True}, FilterBinding(user_key="alice")) == [
        FilterCondition("created_by", "exact", "alice")
    ]
    assert f.describe({"is_owner": True}) == "Mine only"
    assert f.describe({}) is None


def test_is_owner_filter_several_fields_compile_to_any_of() -> None:
    f = IsOwnerFilter(owner_fields=["created_by", "assigned_to", "created_by"])

    assert f.owner_fields == ("created_by", "assigned_to")
    assert f.compile({"is_owner": True}, FilterBinding(user_key=7)) == [
        FilterCondition("created_by", "any_of", (("created_by", 7), ("assigned_to", 7)))
    ]


def test_is_owner_filter_needs_an_owner_field() -> None:
    with pytest.raises(ValueError, match="at least one owner field"):
        IsOwnerFilter(owner_fields=[" "])


def test_is_owner_filter_renders_a_switch_with_help() -> None:
    f = IsOwnerFilter(owner_fields="created_by", help_text="Orders where you are the sales rep.")

    html = f.render(FilterRenderContext(query={"is_owner": "1"}))

    assert 'role="switch" name="is_owner" value="1" checked data-testid="filter-is_owner"' in html
    assert "Orders where you are the sales rep." in html
    assert "ha-help" not in IsOwnerFilter(owner_fields="created_by").render(
        FilterRenderContext(query={})
    )


# ---------------------------------------------------------------------------
# core/filters_compat
# ---------------------------------------------------------------------------


def test_legacy_string_is_wrapped_into_a_filter_def() -> None:
    """
    Scenario: legacy list_filter=["status"] is wrapped into a FilterDef
      Given AdminOptions(list_filter=["status"])
      When  the list view collects filters
      Then  filters[0] is an instance of FilterDef
      And   filters[0].field == "status"
    """
    explicit = DateRangeFilter(field="created_at")

    filters = collect_filters(["status", explicit])

    assert isinstance(filters[0], FilterDef)
    assert isinstance(filters[0], LegacyFieldFilter)
    assert filters[0].field == "status"
    assert filters[1] is explicit
    assert collect_filters(None) == []
    with pytest.raises(TypeError, match="str or FilterDef"):
        collect_filters([42])  # type: ignore[list-item]


def test_legacy_filter_keeps_the_filter_prefix_contract() -> None:
    f = LegacyFieldFilter(field="status")

    assert f.query_keys == ("filter_status",)
    assert f.parse({"filter_status": "done"}) == {"value": "done"}
    assert f.parse({}) == {}
    assert f.compile({"value": "done"}, _binding()) == [
        FilterCondition("status", "exact", Status.DONE)
    ]
    assert f.compile({}, _binding()) == []
    assert f.describe({"value": "done"}) == "done"


def test_legacy_filter_renders_a_select_with_the_current_choice() -> None:
    f = LegacyFieldFilter(field="status")
    ctx = FilterRenderContext(
        query={"filter_status": "done"}, choices=_choices(("draft", "Draft"), ("done", "Done"))
    )

    html = f.render(ctx)

    assert (
        'name="filter_status" class="ha-select" aria-label="Status" data-testid="filter-status"'
        in html
    )
    assert '<option value="done" selected>Done</option>' in html
    assert '<option value="draft">Draft</option>' in html
