"""Unit tests for ``hyperadmin.core.filtering``."""

from __future__ import annotations

import ast
import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import DateTime, Integer, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from hyperadmin.core import FilterCondition, FilterValueError
from hyperadmin.core.filtering import (
    ParsedFilters,
    coerce_filter_value,
    normalize_filters,
    parse_filter_params,
)

UTC = timezone.utc
AMS = ZoneInfo("Europe/Amsterdam")


class Status(enum.Enum):
    DRAFT = "draft"
    DONE = "done"


class Priority(int, enum.Enum):
    LOW = 1
    HIGH = 2


class Order(BaseModel):
    id: int
    quantity: int = 0
    price: Decimal = Decimal(0)
    ratio: float = 0.0
    is_active: bool = True
    status: Status = Status.DRAFT
    customer_id: uuid.UUID | None = None
    created_at: datetime | None = None
    shipped_on: date | None = None
    note: str = ""
    password_hash: str = ""
    tagged: Annotated[int, Field(ge=0)] = 0


def _naive_kind(field: str) -> str | None:
    return "naive" if field == "created_at" else None


def _aware_kind(field: str) -> str | None:
    return "aware" if field == "created_at" else None


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-19)
# ---------------------------------------------------------------------------


def test_integer_value_is_coerced() -> None:
    """
    Scenario: integer value is coerced
      Given annotation int
      When  coerce_filter_value(int, '3') runs
      Then  3 is returned
    """
    result = coerce_filter_value(int, "3")

    assert result == 3
    assert isinstance(result, int)


def test_uuid_parse_error_names_the_field() -> None:
    """
    Scenario: UUID parse error
      Given annotation UUID
      When  raw is 'not-a-uuid'
      Then  FilterValueError names the field
    """
    with pytest.raises(FilterValueError) as excinfo:
        coerce_filter_value(uuid.UUID, "not-a-uuid", field="customer_id")

    assert excinfo.value.field == "customer_id"
    assert "customer_id" in str(excinfo.value)

    parsed = parse_filter_params(Order, {"filter_customer_id": "not-a-uuid"}, ["customer_id"])
    assert parsed.conditions == []
    assert "customer_id" in parsed.errors


def test_range_params_parse() -> None:
    """
    Scenario: range params parse
      Given params filter_created_at__gte and __lte with created_at allowed
      When  parse_filter_params runs
      Then  two conditions gte and lte are returned
    """
    params = {
        "filter_created_at__gte": "2026-01-01",
        "filter_created_at__lte": "2026-01-31",
    }

    parsed = parse_filter_params(Order, params, ["created_at"])

    assert parsed.conditions == [
        FilterCondition("created_at", "gte", datetime(2026, 1, 1)),
        FilterCondition("created_at", "lte", datetime(2026, 1, 31, 23, 59, 59, 999999)),
    ]
    assert parsed.errors == {}


def test_non_whitelisted_field_is_ignored() -> None:
    """
    Scenario: non-whitelisted field is ignored
      Given allowed=['is_active']
      When  params contain filter_password_hash
      Then  no condition is produced
    """
    parsed = parse_filter_params(Order, {"filter_password_hash": "abc"}, ["is_active"])

    assert parsed.conditions == []
    assert parsed.active == {}
    assert parsed.errors == {}


# ---------------------------------------------------------------------------
# coerce_filter_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("annotation", "raw", "expected"),
    [
        (bool, "true", True),
        (bool, "False", False),
        (bool, "1", True),
        (bool, "off", False),
        (int, " 42 ", 42),
        (float, "1.5", 1.5),
        (Decimal, "9.99", Decimal("9.99")),
        (
            uuid.UUID,
            "12345678123456781234567812345678",
            uuid.UUID(int=0x12345678123456781234567812345678),
        ),
        (Status, "done", Status.DONE),
        (Status, "DONE", Status.DONE),
        (Priority, "2", Priority.HIGH),
        (date, "2026-01-02", date(2026, 1, 2)),
        (datetime, "2026-01-02T03:04:05", datetime(2026, 1, 2, 3, 4, 5)),
        (datetime, "2026-01-02T03:04:05Z", datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)),
        (AwareDatetime, "2026-01-02T03:04:05+00:00", datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)),
        (str, "abc", "abc"),
        (int | None, "7", 7),
        (Annotated[int, Field(ge=0)], "5", 5),
        (Any, "raw", "raw"),
        (None, "raw", "raw"),
        (list[int], "raw", "raw"),
    ],
)
def test_coerce_filter_value(annotation: Any, raw: str, expected: Any) -> None:
    assert coerce_filter_value(annotation, raw) == expected


@pytest.mark.parametrize(
    ("annotation", "raw"),
    [
        (bool, "maybe"),
        (int, "3.5"),
        (int, "abc"),
        (float, "x"),
        (Decimal, "1,5"),
        (Decimal, "NaN"),
        (Status, "archived"),
        (date, "2026-02-30"),
        (datetime, "yesterday"),
        (uuid.UUID, "123"),
    ],
)
def test_coerce_filter_value_rejects_bad_input(annotation: Any, raw: str) -> None:
    with pytest.raises(FilterValueError):
        coerce_filter_value(annotation, raw)


def test_filter_value_error_is_a_value_error() -> None:
    assert issubclass(FilterValueError, ValueError)
    assert FilterValueError("bad", field=None).field is None


# ---------------------------------------------------------------------------
# FilterCondition / normalize_filters
# ---------------------------------------------------------------------------


def test_filter_condition_rejects_unknown_operator() -> None:
    with pytest.raises(ValueError, match="operator"):
        FilterCondition("quantity", "like", "3")  # type: ignore[arg-type]


def test_filter_condition_is_frozen() -> None:
    condition = FilterCondition("quantity", "exact", 3)

    with pytest.raises(AttributeError):
        condition.value = 4  # type: ignore[misc]


def test_normalize_filters_none() -> None:
    assert normalize_filters(None) == []


def test_normalize_filters_legacy_dict() -> None:
    assert normalize_filters({"quantity": 3, "is_active": True}) == [
        FilterCondition("quantity", "exact", 3),
        FilterCondition("is_active", "exact", True),
    ]


def test_normalize_filters_sequence() -> None:
    conditions = (FilterCondition("quantity", "gte", 3),)

    assert normalize_filters(conditions) == [FilterCondition("quantity", "gte", 3)]


def test_normalize_filters_rejects_foreign_items() -> None:
    with pytest.raises(TypeError):
        normalize_filters([("quantity", 3)])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# parse_filter_params
# ---------------------------------------------------------------------------


def test_exact_filter_keeps_legacy_active_key() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity": "3", "page": "2"}, ["quantity"])

    assert parsed == ParsedFilters(
        conditions=[FilterCondition("quantity", "exact", 3)],
        active={"quantity": "3"},
        errors={},
    )


def test_explicit_exact_operator() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity__exact": "3"}, ["quantity"])

    assert parsed.conditions == [FilterCondition("quantity", "exact", 3)]


def test_empty_values_are_skipped() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity": ""}, ["quantity"])

    assert parsed.conditions == []
    assert parsed.active == {}


def test_bool_filter() -> None:
    parsed = parse_filter_params(Order, {"filter_is_active": "false"}, ["is_active"])

    assert parsed.conditions == [FilterCondition("is_active", "exact", False)]


def test_in_operator_splits_and_repeats() -> None:
    params = [
        ("filter_quantity__in", "1,2"),
        ("filter_quantity__in", "3"),
    ]

    parsed = parse_filter_params(Order, params, ["quantity"])

    assert parsed.conditions == [FilterCondition("quantity", "in", (1, 2, 3))]
    assert parsed.active == {"quantity__in": "1,2,3"}


def test_in_operator_reads_multi_items() -> None:
    class _QueryParams:
        def multi_items(self) -> list[tuple[str, str]]:
            return [("filter_status__in", "draft"), ("filter_status__in", "done")]

    parsed = parse_filter_params(Order, _QueryParams(), ["status"])

    assert parsed.conditions == [FilterCondition("status", "in", (Status.DRAFT, Status.DONE))]


def test_mapping_with_list_values() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity__in": ["4", "5"]}, ["quantity"])

    assert parsed.conditions == [FilterCondition("quantity", "in", (4, 5))]


def test_in_operator_with_a_bad_item_drops_the_condition() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity__in": "1,x"}, ["quantity"])

    assert parsed.conditions == []
    assert "quantity" in parsed.errors


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("false", False)])
def test_isnull_operator(raw: str, expected: bool) -> None:
    parsed = parse_filter_params(Order, {"filter_customer_id__isnull": raw}, ["customer_id"])

    assert parsed.conditions == [FilterCondition("customer_id", "isnull", expected)]


def test_unknown_operator_suffix_is_treated_as_field_name() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity__like": "3"}, ["quantity"])

    assert parsed.conditions == []


def test_unknown_model_field_is_ignored_even_if_allowed() -> None:
    parsed = parse_filter_params(Order, {"filter_ghost": "1"}, ["ghost"])

    assert parsed.conditions == []
    assert parsed.errors == {}


def test_non_filter_params_are_ignored() -> None:
    parsed = parse_filter_params(Order, {"search": "x", "sort_by": "id"}, ["quantity"])

    assert parsed.conditions == []


def test_bad_value_records_error_and_keeps_active_value() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity__gte": "many"}, ["quantity"])

    assert parsed.conditions == []
    assert parsed.active == {"quantity__gte": "many"}
    assert "quantity" in parsed.errors


def test_exact_date_on_datetime_column_becomes_a_day_range() -> None:
    parsed = parse_filter_params(Order, {"filter_created_at": "2026-01-05"}, ["created_at"])

    assert parsed.conditions == [
        FilterCondition("created_at", "gte", datetime(2026, 1, 5)),
        FilterCondition("created_at", "lte", datetime(2026, 1, 5, 23, 59, 59, 999999)),
    ]
    assert parsed.active == {"created_at": "2026-01-05"}


def test_date_bounds_on_aware_columns_use_the_display_timezone() -> None:
    params = {"filter_created_at__gte": "2026-07-01", "filter_created_at__lte": "2026-07-01"}

    parsed = parse_filter_params(Order, params, ["created_at"], tz=AMS, datetime_kind=_aware_kind)

    assert parsed.conditions == [
        FilterCondition("created_at", "gte", datetime(2026, 6, 30, 22, 0, tzinfo=UTC)),
        FilterCondition("created_at", "lte", datetime(2026, 7, 1, 21, 59, 59, 999999, tzinfo=UTC)),
    ]


def test_datetime_bounds_on_aware_columns_are_localised() -> None:
    parsed = parse_filter_params(
        Order,
        {"filter_created_at__gte": "2026-07-01T10:00"},
        ["created_at"],
        tz=AMS,
        datetime_kind=_aware_kind,
    )

    assert parsed.conditions == [
        FilterCondition("created_at", "gte", datetime(2026, 7, 1, 8, 0, tzinfo=UTC))
    ]


def test_datetime_bounds_on_naive_columns_keep_wall_clock() -> None:
    parsed = parse_filter_params(
        Order,
        {"filter_created_at__lte": "2026-07-01T10:00"},
        ["created_at"],
        tz=AMS,
        datetime_kind=_naive_kind,
    )

    assert parsed.conditions == [FilterCondition("created_at", "lte", datetime(2026, 7, 1, 10, 0))]


def test_date_column_range() -> None:
    parsed = parse_filter_params(Order, {"filter_shipped_on__gte": "2026-01-01"}, ["shipped_on"])

    assert parsed.conditions == [FilterCondition("shipped_on", "gte", date(2026, 1, 1))]


def test_model_without_model_fields_passes_raw_values() -> None:
    class Plain:
        pass

    parsed = parse_filter_params(Plain, {"filter_code": "A1"}, ["code"])

    assert parsed.conditions == [FilterCondition("code", "exact", "A1")]


def test_filtering_module_is_pure() -> None:
    tree = ast.parse(Path("src/hyperadmin/core/filtering.py").read_text())
    modules = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    forbidden = (
        "sqlalchemy",
        "sqlmodel",
        "fastapi",
        "starlette",
        "hyperadmin.adapters",
        "hyperadmin.views",
    )
    assert not [m for m in modules if m.startswith(forbidden)]


def test_aware_annotation_is_aware_without_a_resolver() -> None:
    class Event(BaseModel):
        at: AwareDatetime | None = None

    parsed = parse_filter_params(Event, {"filter_at__gte": "2026-07-01T10:00"}, ["at"], tz=AMS)

    assert parsed.conditions == [
        FilterCondition("at", "gte", datetime(2026, 7, 1, 8, 0, tzinfo=UTC))
    ]


@pytest.mark.parametrize(
    "key",
    ["filter_created_at", "filter_created_at__gte", "filter_created_at__lte"],
)
@pytest.mark.parametrize("raw", ["2026-02-30", "soon"])
def test_invalid_datetime_values_record_errors(key: str, raw: str) -> None:
    parsed = parse_filter_params(Order, {key: raw}, ["created_at"])

    assert parsed.conditions == []
    assert "created_at" in parsed.errors


def test_in_operator_with_only_separators_is_skipped() -> None:
    parsed = parse_filter_params(Order, {"filter_quantity__in": " , "}, ["quantity"])

    assert parsed == ParsedFilters()


# ---------------------------------------------------------------------------
# Out-of-range values (review of st-v058-byoa-19)
# ---------------------------------------------------------------------------

NYC = ZoneInfo("America/New_York")


class Stamped(BaseModel):
    ts: AwareDatetime | None = None
    n: datetime | None = None


@pytest.mark.parametrize(
    ("key", "raw", "tz"),
    [
        ("filter_ts", "9999-12-31", NYC),
        ("filter_ts__lte", "9999-12-31", NYC),
        ("filter_ts__gte", "9999-12-31", NYC),
        ("filter_ts", "0001-01-01", AMS),
        ("filter_ts__gte", "0001-01-01", AMS),
        ("filter_ts__gte", "9999-12-31T23:00:00-05:00", UTC),
        ("filter_ts__in", "2026-01-01,9999-12-31", NYC),
        ("filter_n__gte", "0001-01-01T00:00:00+05:00", UTC),
        ("filter_n__lte", "9999-12-31T23:00:00-05:00", AMS),
    ],
)
def test_out_of_range_datetimes_record_errors(key: str, raw: str, tz: ZoneInfo) -> None:
    """
    Scenario: a value that overflows on conversion drops its condition
      Given a datetime filter value at the edge of the supported date range
      When  parse_filter_params converts it to UTC or the display timezone
      Then  no condition is produced and the field records an error
    """
    field_name = key[len("filter_") :].split("__", maxsplit=1)[0]

    parsed = parse_filter_params(Stamped, {key: raw}, ["ts", "n"], tz=tz)

    assert parsed.conditions == []
    assert field_name in parsed.errors


# ---------------------------------------------------------------------------
# Annotation resolver for non-pydantic models (review of st-v058-byoa-19)
# ---------------------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class SaOrder(_Base):
    __tablename__ = "filtering_sa_order"
    id: Mapped[int] = mapped_column(primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime)


def _sa_annotation(name: str) -> Any:
    column = SaOrder.__table__.columns.get(name)
    return column.type.python_type if column is not None else None


def test_annotation_resolver_coerces_declarative_models() -> None:
    """
    Scenario: plain SQLAlchemy models get typed filters through a resolver
      Given a DeclarativeBase model with int, UUID and DateTime columns
      And   an annotation_of resolver returning each column's python type
      When  parse_filter_params runs
      Then  '3' becomes 3 and a date-only bound becomes a datetime
      And   an invalid UUID is recorded as an error
    """
    parsed = parse_filter_params(
        SaOrder,
        {
            "filter_quantity": "3",
            "filter_customer_id": "not-a-uuid",
            "filter_created_at__gte": "2026-07-01",
        },
        ["quantity", "customer_id", "created_at"],
        annotation_of=_sa_annotation,
    )

    assert parsed.conditions == [
        FilterCondition("quantity", "exact", 3),
        FilterCondition("created_at", "gte", datetime(2026, 7, 1)),  # noqa: DTZ001
    ]
    assert set(parsed.errors) == {"customer_id"}


def test_annotation_resolver_falls_back_to_model_fields() -> None:
    parsed = parse_filter_params(
        Order, {"filter_quantity": "4"}, ["quantity"], annotation_of=lambda _name: None
    )

    assert parsed.conditions == [FilterCondition("quantity", "exact", 4)]


def test_annotation_resolver_overrides_model_fields() -> None:
    parsed = parse_filter_params(
        Order, {"filter_note": "7"}, ["note"], annotation_of=lambda _name: int
    )

    assert parsed.conditions == [FilterCondition("note", "exact", 7)]
