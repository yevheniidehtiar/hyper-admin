"""``BaseAdapter.list()`` applies ``FilterCondition`` lists with dict back-compat.

Covers story ``st-v058-byoa-24``: ``adapters/_filter_clause.build_clause(s)``,
shared by ``SQLModelAdapter`` and ``SQLAlchemyAdapter``, compiles either the
legacy ``{column: value}`` equality mapping or a ``Sequence[FilterCondition]``
(``core/filtering.py``, story st-v058-byoa-19) to SQLAlchemy clauses. The
review amendment generalizes ``adapters/introspection.coerce_column_value``
(renamed from ``coerce_cascade_filter_value``) to coerce any cascade-filter
value — not only UUIDs — via ``core.filtering.coerce_filter_value``.

Every ``list()`` scenario runs against both adapters.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.inspection import inspect as sa_inspect
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.introspection import coerce_column_value
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.filtering import FilterCondition, FilterValueError

AdapterClass = type[SQLModelAdapter] | type[SQLAlchemyAdapter]

# ---------------------------------------------------------------------------
# Schema fixtures
# ---------------------------------------------------------------------------


class Category(str, enum.Enum):
    GADGET = "gadget"
    TOOL = "tool"


class FilterWarehouse(SQLModel, table=True):
    __tablename__ = "filter_cond_warehouses"

    id: int | None = Field(default=None, primary_key=True)
    name: str

    products: list["FilterProduct"] = Relationship(back_populates="warehouse")


class FilterProduct(SQLModel, table=True):
    __tablename__ = "filter_cond_products"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    quantity: int
    category: Category
    is_active: bool = True
    price: Decimal = Decimal(0)
    deleted_at: datetime | None = None
    warehouse_id: int | None = Field(default=None, foreign_key="filter_cond_warehouses.id")

    warehouse: FilterWarehouse | None = Relationship(back_populates="products")


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_class(request: pytest.FixtureRequest) -> AdapterClass:
    return request.param


@pytest.fixture
async def warehouse(engine: AsyncEngine) -> Any:
    adapter = SQLModelAdapter(FilterWarehouse, engine)
    return await adapter.create({"name": "Main"})


@pytest.fixture
async def products(engine: AsyncEngine, warehouse: Any) -> list[Any]:
    """Four rows spanning every operator this story exercises.

    - Widget A: quantity=1,  TOOL,   active,   deleted_at=None
    - Widget B: quantity=3,  GADGET, active,   deleted_at=None
    - Widget C: quantity=4,  GADGET, inactive, deleted_at=2024-01-01
    - Widget D: quantity=10, TOOL,   active,   deleted_at=None
    """
    adapter = SQLModelAdapter(FilterProduct, engine)
    rows = [
        {
            "name": "Widget A",
            "quantity": 1,
            "category": Category.TOOL,
            "is_active": True,
            "deleted_at": None,
            "warehouse_id": warehouse.id,
        },
        {
            "name": "Widget B",
            "quantity": 3,
            "category": Category.GADGET,
            "is_active": True,
            "deleted_at": None,
            "warehouse_id": warehouse.id,
        },
        {
            "name": "Widget C",
            "quantity": 4,
            "category": Category.GADGET,
            "is_active": False,
            "deleted_at": datetime(2024, 1, 1),
            "warehouse_id": warehouse.id,
        },
        {
            "name": "Widget D",
            "quantity": 10,
            "category": Category.TOOL,
            "is_active": True,
            "deleted_at": None,
            "warehouse_id": warehouse.id,
        },
    ]
    return [await adapter.create(row) for row in rows]


# ---------------------------------------------------------------------------
# Scenario: legacy dict filters still work
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_legacy_dict_filters_still_work(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: legacy dict filters still work
      Given adapter.list(filters={'is_active': True})
      When  list() runs
      Then  only active rows are returned
    """
    adapter = adapter_class(FilterProduct, engine)

    items, total = await adapter.list(filters={"is_active": True})

    assert total == 3
    assert {item.name for item in items} == {"Widget A", "Widget B", "Widget D"}


# ---------------------------------------------------------------------------
# Scenario: range condition applies
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_range_condition_applies(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: range condition applies
      Given conditions quantity gte 2 and lte 4
      When  list() runs
      Then  only rows with 2<=quantity<=4 are returned
    """
    adapter = adapter_class(FilterProduct, engine)

    items, total = await adapter.list(
        filters=[
            FilterCondition("quantity", "gte", 2),
            FilterCondition("quantity", "lte", 4),
        ]
    )

    assert total == 2
    assert {item.name for item in items} == {"Widget B", "Widget C"}


# ---------------------------------------------------------------------------
# Scenario: isnull condition applies
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_isnull_true_condition_applies(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: isnull condition applies
      Given condition deleted_at isnull true
      When  list() runs
      Then  only rows with a NULL deleted_at are returned
    """
    adapter = adapter_class(FilterProduct, engine)

    items, total = await adapter.list(filters=[FilterCondition("deleted_at", "isnull", True)])

    assert total == 3
    assert {item.name for item in items} == {"Widget A", "Widget B", "Widget D"}


@pytest.mark.anyio
async def test_isnull_false_condition_applies(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: isnull false condition applies
      Given condition deleted_at isnull false
      When  list() runs
      Then  only rows with a non-NULL deleted_at are returned

    Exercises the other branch of build_clause's isnull ternary (the required
    scenario above only exercises isnull=True).
    """
    adapter = adapter_class(FilterProduct, engine)

    items, total = await adapter.list(filters=[FilterCondition("deleted_at", "isnull", False)])

    assert total == 1
    assert items[0].name == "Widget C"


# ---------------------------------------------------------------------------
# Scenario: in condition applies (build_clause's remaining branch)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_in_condition_applies(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: in condition applies
      Given condition category in (gadget,)
      When  list() runs
      Then  only rows whose category is in the set are returned
    """
    adapter = adapter_class(FilterProduct, engine)

    items, total = await adapter.list(
        filters=[FilterCondition("category", "in", (Category.GADGET,))]
    )

    assert total == 2
    assert {item.name for item in items} == {"Widget B", "Widget C"}


# ---------------------------------------------------------------------------
# Scenario: FilterCondition list and legacy dict combine with get_queryset
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_filters_list_matches_no_narrowing(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: no filters means no narrowing
      Given adapter.list(filters=None)
      When  list() runs
      Then  every row is returned
    """
    adapter = adapter_class(FilterProduct, engine)

    items, total = await adapter.list()

    assert total == 4
    assert len(items) == 4


# ---------------------------------------------------------------------------
# Review amendment: coerce_column_value generalizes cascade-filter coercion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_choices_cascade_filter_coerces_enum_value(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: enum cascade filter value is coerced before comparison
      Given a cascade filter category='gadget' (a plain str query value)
      When  get_choices runs on the warehouse's products relation
      Then  only gadget-category products are returned

    Before the review amendment, only UUID columns were coerced
    (``coerce_cascade_filter_value``); an Enum column compared the raw str
    against the column's Enum values, which some backends would not match.
    """
    adapter = adapter_class(FilterWarehouse, engine)

    choices = await adapter.get_choices("products", category="gadget")

    assert {c["label"] for c in choices} == {"Widget B", "Widget C"}


@pytest.mark.anyio
async def test_choices_cascade_filter_coerces_bool_value(
    engine: AsyncEngine, products: list[Any], adapter_class: AdapterClass
) -> None:
    """
    Scenario: bool cascade filter value is coerced before comparison
      Given a cascade filter is_active='false' (a plain str query value)
      When  get_choices runs on the warehouse's products relation
      Then  only inactive products are returned
    """
    adapter = adapter_class(FilterWarehouse, engine)

    choices = await adapter.get_choices("products", is_active="false")

    assert {c["label"] for c in choices} == {"Widget C"}


# ---------------------------------------------------------------------------
# Direct unit tests for coerce_column_value (every branch)
# ---------------------------------------------------------------------------


def test_coerce_column_value_passes_through_non_str_raw() -> None:
    """
    Scenario: a non-str raw value passes through unchanged
      Given raw=5 (already a Python int, not query-string text)
      When  coerce_column_value runs
      Then  5 is returned unchanged
    """
    mapper = sa_inspect(FilterProduct)

    assert coerce_column_value(mapper, "quantity", 5) == 5


def test_coerce_column_value_passes_through_unknown_attr() -> None:
    """
    Scenario: an attribute absent from the mapper's columns passes through
      Given attr='not_a_column'
      When  coerce_column_value runs
      Then  the raw string is returned unchanged
    """
    mapper = sa_inspect(FilterProduct)

    assert coerce_column_value(mapper, "not_a_column", "whatever") == "whatever"


def test_coerce_column_value_passes_through_str_column() -> None:
    """
    Scenario: a str-typed column's value passes through unchanged
      Given attr='name' (a str column)
      When  coerce_column_value runs
      Then  the raw string is returned unchanged
    """
    mapper = sa_inspect(FilterProduct)

    assert coerce_column_value(mapper, "name", "Widget A") == "Widget A"


def test_coerce_column_value_coerces_decimal() -> None:
    """
    Scenario: a Decimal-typed column's value is coerced
      Given attr='price' and raw='12.50'
      When  coerce_column_value runs
      Then  Decimal('12.50') is returned
    """
    mapper = sa_inspect(FilterProduct)

    assert coerce_column_value(mapper, "price", "12.50") == Decimal("12.50")


def test_coerce_column_value_coerces_date() -> None:
    """
    Scenario: a datetime-typed column's value is coerced
      Given attr='deleted_at' and raw='2024-01-01'
      When  coerce_column_value runs
      Then  a datetime matching that day is returned
    """
    mapper = sa_inspect(FilterProduct)

    coerced = coerce_column_value(mapper, "deleted_at", "2024-01-01")

    assert coerced == datetime(2024, 1, 1)


def test_coerce_column_value_coerces_uuid() -> None:
    """
    Scenario: a UUID-typed column's value is coerced
      Given a UUID-keyed model and a valid UUID string
      When  coerce_column_value runs
      Then  a uuid.UUID instance is returned
    """

    class _UuidKeyed(SQLModel, table=True):
        __tablename__ = "filter_cond_uuid_keyed"
        id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    mapper = sa_inspect(_UuidKeyed)
    raw = str(uuid.uuid4())

    assert coerce_column_value(mapper, "id", raw) == uuid.UUID(raw)


def test_coerce_column_value_rejects_bad_uuid() -> None:
    """
    Scenario: an unparseable UUID cascade value raises FilterValueError
      Given a UUID-keyed model and an invalid UUID string
      When  coerce_column_value runs
      Then  FilterValueError (a ValueError subclass) is raised
    """

    class _UuidKeyed2(SQLModel, table=True):
        __tablename__ = "filter_cond_uuid_keyed_2"
        id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    mapper = sa_inspect(_UuidKeyed2)

    with pytest.raises(FilterValueError):
        coerce_column_value(mapper, "id", "garbage")


def test_coerce_column_value_coerces_date_type_field() -> None:
    """
    Scenario: a pure ``date`` column's value is coerced to ``date``
      Given a date-typed column and a valid ISO date string
      When  coerce_column_value runs
      Then  a date (not datetime) instance is returned
    """

    class _DatedModel(SQLModel, table=True):
        __tablename__ = "filter_cond_dated"
        id: int | None = Field(default=None, primary_key=True)
        on_date: date

    mapper = sa_inspect(_DatedModel)

    assert coerce_column_value(mapper, "on_date", "2024-06-15") == date(2024, 6, 15)
