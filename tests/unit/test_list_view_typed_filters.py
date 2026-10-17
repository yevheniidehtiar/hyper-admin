"""Typed, whitelisted filters in ``list_view`` (st-v058-byoa-44).

Spec: ``docs/specs/bring-your-own-app.md`` section D.3 (and Owner decisions 7
and 8: only ``list_filter`` fields are filterable, and this milestone ships the
``exact`` operator only).

``list_view`` parses ``filter_*`` query parameters with
:func:`hyperadmin.core.filtering.parse_filter_params`, passes the resulting
:class:`FilterCondition` list to the adapter and exposes per-field
``filter_errors`` in the template context while the page still returns 200.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.filtering import FilterCondition, parse_filter_params
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.template_filters import request_tz

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

CUSTOMER_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
CUSTOMER_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TfOrder(SQLModel, table=True):
    __tablename__ = "typed_filter_order"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    quantity: int = 0
    customer_id: uuid.UUID | None = None
    created_at: datetime | None = None
    placed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore[call-overload]


class TfUser(SQLModel, table=True):
    __tablename__ = "typed_filter_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = ""
    password_hash: str = ""
    is_active: bool = True


class TfOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class TfUserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


ORDERS: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "o-one",
        "quantity": 1,
        "customer_id": CUSTOMER_A,
        "created_at": datetime(2026, 1, 15, 0, 0),
    },
    {
        "id": 2,
        "title": "o-two",
        "quantity": 3,
        "customer_id": CUSTOMER_B,
        "created_at": datetime(2026, 1, 15, 18, 30),
    },
    {
        "id": 3,
        "title": "o-three",
        "quantity": 3,
        "customer_id": CUSTOMER_A,
        "created_at": datetime(2026, 1, 16, 9, 0),
    },
]
USERS: list[dict[str, Any]] = [
    {"id": 1, "username": "u-alice", "password_hash": "abc", "is_active": True},
    {"id": 2, "username": "u-bob", "password_hash": "xyz", "is_active": False},
]


@pytest.fixture(autouse=True)
def _clean() -> Any:
    site._registry = {}
    yield
    site._registry = {}


async def _seed(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=[TfOrder.__table__, TfUser.__table__],  # type: ignore[attr-defined]
        )
    async with AsyncSession(engine) as session:
        # Fresh instances per test: a table model carries SQLAlchemy state, so a
        # shared module-level instance would not be inserted a second time.
        session.add_all([TfOrder(**row) for row in ORDERS])
        session.add_all([TfUser(**row) for row in USERS])
        await session.commit()


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record the ``filters`` argument every ``SQLModelAdapter.list`` call receives."""
    calls: list[Any] = []
    original = SQLModelAdapter.list

    async def _list(self: SQLModelAdapter, *args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs.get("filters"))
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(SQLModelAdapter, "list", _list)
    return calls


def _client(*, tz: str = "UTC", app: FastAPI | None = None) -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine)
    app = app or FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, timezone=tz),
    )
    site.register(
        TfOrder,
        TfOrderAdmin,
        options=AdminOptions(
            list_display=["title", "quantity"],
            list_filter=["quantity", "customer_id", "created_at", "placed_at"],
        ),
    )
    site.register(
        TfUser,
        TfUserAdmin,
        options=AdminOptions(list_display=["username"], list_filter=["is_active"]),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def _titles(html: str, prefix: str) -> list[str]:
    seen: list[str] = []
    for name in re.findall(rf">({prefix}-[a-z]+)<", html):
        if name not in seen:
            seen.append(name)
    return sorted(seen)


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_integer_filter_coerced(spy: list[Any]) -> None:
    """
    Scenario: integer filter coerced
      Given Order list_filter ['quantity']
      When  /admin/order?filter_quantity=3 is requested
      Then  only quantity 3 rows are listed
    """
    # Given Order list_filter ['quantity']
    client = _client()

    # When /admin/order?filter_quantity=3 is requested
    resp = client.get("/admin/tforder?filter_quantity=3")

    # Then only quantity 3 rows are listed
    assert resp.status_code == 200
    assert _titles(resp.text, "o") == ["o-three", "o-two"]
    assert spy[-1] == [FilterCondition("quantity", "exact", 3)]
    assert resp.context["active_filters"] == {"quantity": "3"}  # type: ignore[attr-defined]
    assert resp.context["filter_errors"] == {}  # type: ignore[attr-defined]


def test_repeated_exact_filter_uses_the_last_value(spy: list[Any]) -> None:
    """
    Scenario: repeated exact filter uses the last value
      Given Order list_filter ['quantity']
      When  /admin/order?filter_quantity=1&filter_quantity=3 is requested
      Then  only quantity 3 rows are listed
      And   the active filter re-rendered into links is the same value 3
    """
    # Given Order list_filter ['quantity']
    client = _client()

    # When /admin/order?filter_quantity=1&filter_quantity=3 is requested
    resp = client.get("/admin/tforder?filter_quantity=1&filter_quantity=3")

    # Then only quantity 3 rows are listed
    assert resp.status_code == 200
    assert _titles(resp.text, "o") == ["o-three", "o-two"]
    assert spy[-1] == [FilterCondition("quantity", "exact", 3)]
    # And the active filter re-rendered into links is the same value 3
    assert resp.context["active_filters"] == {"quantity": "3"}  # type: ignore[attr-defined]
    assert resp.context["filter_errors"] == {}  # type: ignore[attr-defined]


def test_non_whitelisted_ignored(spy: list[Any]) -> None:
    """
    Scenario: non-whitelisted ignored
      Given User list_filter ['is_active']
      When  /admin/user?filter_password_hash=abc is requested
      Then  all users are listed
    """
    # Given User list_filter ['is_active']
    client = _client()

    # When /admin/user?filter_password_hash=abc is requested
    resp = client.get("/admin/tfuser?filter_password_hash=abc")

    # Then all users are listed
    assert resp.status_code == 200
    assert _titles(resp.text, "u") == ["u-alice", "u-bob"]
    assert spy[-1] == []
    assert resp.context["active_filters"] == {}  # type: ignore[attr-defined]


def test_invalid_uuid_keeps_page_working(spy: list[Any]) -> None:
    """
    Scenario: invalid UUID keeps page working
      Given Order list_filter ['customer_id'] of type UUID
      When  filter_customer_id=not-a-uuid is requested
      Then  the status is 200
      And   filter_errors contains customer_id
    """
    # Given Order list_filter ['customer_id'] of type UUID
    client = _client()

    # When filter_customer_id=not-a-uuid is requested
    resp = client.get("/admin/tforder?filter_customer_id=not-a-uuid")

    # Then the status is 200
    assert resp.status_code == 200
    # And filter_errors contains customer_id
    errors = resp.context["filter_errors"]  # type: ignore[attr-defined]
    assert set(errors) == {"customer_id"}
    assert "UUID" in errors["customer_id"]
    # The invalid condition is dropped, so every row is listed and the raw
    # value is kept for re-rendering the filter input.
    assert spy[-1] == []
    assert _titles(resp.text, "o") == ["o-one", "o-three", "o-two"]
    assert resp.context["active_filters"] == {"customer_id": "not-a-uuid"}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Further D.3 rules
# ---------------------------------------------------------------------------


def test_valid_uuid_filter_is_coerced(spy: list[Any]) -> None:
    """
    Scenario: a valid UUID filter value is coerced to UUID
      Given Order list_filter ['customer_id'] of type UUID
      When  filter_customer_id=<customer B> is requested
      Then  only that customer's orders are listed
    """
    # Given Order list_filter ['customer_id'] of type UUID
    client = _client()

    # When filter_customer_id=<customer B> is requested
    resp = client.get(f"/admin/tforder?filter_customer_id={CUSTOMER_B}")

    # Then only that customer's orders are listed
    assert resp.status_code == 200
    assert _titles(resp.text, "o") == ["o-two"]
    assert spy[-1] == [FilterCondition("customer_id", "exact", CUSTOMER_B)]


def test_one_invalid_filter_does_not_drop_the_valid_ones(spy: list[Any]) -> None:
    """
    Scenario: a valid filter still applies next to an invalid one
      Given Order list_filter ['quantity', 'customer_id']
      When  filter_quantity=3&filter_customer_id=nope is requested
      Then  the quantity filter applies
      And   filter_errors names only customer_id
    """
    # Given Order list_filter ['quantity', 'customer_id']
    client = _client()

    # When filter_quantity=3&filter_customer_id=nope is requested
    resp = client.get("/admin/tforder?filter_quantity=3&filter_customer_id=nope")

    # Then the quantity filter applies
    assert _titles(resp.text, "o") == ["o-three", "o-two"]
    assert spy[-1] == [FilterCondition("quantity", "exact", 3)]
    # And filter_errors names only customer_id
    assert set(resp.context["filter_errors"]) == {"customer_id"}  # type: ignore[attr-defined]


def test_invalid_filter_on_an_htmx_partial_is_200_with_errors() -> None:
    """
    Scenario: an HTMX table refresh with an invalid filter still swaps in
      Given Order list_filter ['quantity']
      When  an HTMX request asks for filter_quantity=abc
      Then  the status is 200
      And   filter_errors contains quantity
    """
    # Given Order list_filter ['quantity']
    client = _client()

    # When an HTMX request asks for filter_quantity=abc
    resp = client.get("/admin/tforder?filter_quantity=abc", headers={"HX-Request": "true"})

    # Then the status is 200
    assert resp.status_code == 200
    # And filter_errors contains quantity
    assert set(resp.context["filter_errors"]) == {"quantity"}  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "query",
    [
        "filter_quantity__gte=2",
        "filter_quantity__lte=1",
        "filter_quantity__in=1,3",
        "filter_customer_id__isnull=true",
    ],
)
def test_range_operators_are_not_accepted_this_milestone(spy: list[Any], query: str) -> None:
    """
    Scenario: range operators are ignored (Owner decision 8: exact only)
      Given Order list_filter ['quantity', 'customer_id']
      When  a filter with a __gte/__lte/__in/__isnull operator is requested
      Then  the operator filter is ignored and every order is listed
    """
    # Given Order list_filter ['quantity', 'customer_id']
    client = _client()

    # When a filter with a __gte/__lte/__in/__isnull operator is requested
    resp = client.get(f"/admin/tforder?{query}")

    # Then the operator filter is ignored and every order is listed
    assert resp.status_code == 200
    assert spy[-1] == []
    assert _titles(resp.text, "o") == ["o-one", "o-three", "o-two"]
    assert resp.context["active_filters"] == {}  # type: ignore[attr-defined]
    assert resp.context["filter_errors"] == {}  # type: ignore[attr-defined]


def test_explicit_exact_operator_is_accepted(spy: list[Any]) -> None:
    """
    Scenario: filter_<f>__exact is the same as filter_<f>
      Given Order list_filter ['quantity']
      When  filter_quantity__exact=1 is requested
      Then  only quantity 1 rows are listed
    """
    # Given Order list_filter ['quantity']
    client = _client()

    # When filter_quantity__exact=1 is requested
    resp = client.get("/admin/tforder?filter_quantity__exact=1")

    # Then only quantity 1 rows are listed
    assert _titles(resp.text, "o") == ["o-one"]
    assert spy[-1] == [FilterCondition("quantity", "exact", 1)]


def test_exact_date_on_a_datetime_column_matches_the_whole_day(spy: list[Any]) -> None:
    """
    Scenario: an exact date on a datetime column matches the whole day
      Given Order list_filter ['created_at'] of type datetime
      When  filter_created_at=2026-01-15 is requested
      Then  every order created on 2026-01-15 is listed, at any time of day
    """
    # Given Order list_filter ['created_at'] of type datetime
    client = _client()

    # When filter_created_at=2026-01-15 is requested
    resp = client.get("/admin/tforder?filter_created_at=2026-01-15")

    # Then every order created on 2026-01-15 is listed, at any time of day
    assert resp.status_code == 200
    assert _titles(resp.text, "o") == ["o-one", "o-two"]
    assert [(c.field, c.op) for c in spy[-1]] == [
        ("created_at", "gte"),
        ("created_at", "lte"),
    ]


def test_date_on_an_aware_column_uses_the_display_timezone(spy: list[Any]) -> None:
    """
    Scenario: a date on an aware column is a local day in the display timezone
      Given the admin's display timezone is Europe/Kyiv (UTC+2 in January)
      And   Order list_filter ['placed_at'] stored timezone-aware
      When  filter_placed_at=2026-01-15 is requested
      Then  the adapter receives the Kyiv day as UTC bounds
    """
    # Given the admin's display timezone is Europe/Kyiv (UTC+2 in January)
    # And Order list_filter ['placed_at'] stored timezone-aware
    client = _client(tz="Europe/Kyiv")

    # When filter_placed_at=2026-01-15 is requested
    resp = client.get("/admin/tforder?filter_placed_at=2026-01-15")

    # Then the adapter receives the Kyiv day as UTC bounds
    assert resp.status_code == 200
    start, end = spy[-1]
    assert (start.field, start.op) == ("placed_at", "gte")
    assert start.value == datetime(2026, 1, 14, 22, 0, tzinfo=timezone.utc)
    assert (end.field, end.op) == ("placed_at", "lte")
    assert end.value == datetime(2026, 1, 15, 21, 59, 59, 999999, tzinfo=timezone.utc)


def test_request_timezone_override_applies_to_filters(spy: list[Any]) -> None:
    """
    Scenario: a per-request timezone override localises filter dates
      Given the admin's display timezone is UTC
      And   a host middleware sets request.state.hyperadmin_timezone to Asia/Tokyo
      When  filter_placed_at=2026-01-15 is requested
      Then  the lower bound is midnight in Tokyo, as UTC
    """
    # Given the admin's display timezone is UTC
    # And a host middleware sets request.state.hyperadmin_timezone to Asia/Tokyo
    app = FastAPI()

    @app.middleware("http")
    async def _tz(request: Request, call_next: Any) -> Any:
        request.state.hyperadmin_timezone = "Asia/Tokyo"
        return await call_next(request)

    client = _client(app=app)

    # When filter_placed_at=2026-01-15 is requested
    resp = client.get("/admin/tforder?filter_placed_at=2026-01-15")

    # Then the lower bound is midnight in Tokyo, as UTC
    assert resp.status_code == 200
    assert spy[-1][0].value == datetime(2026, 1, 14, 15, 0, tzinfo=timezone.utc)


def test_pagination_links_keep_the_active_filter() -> None:
    """
    Scenario: the active filter survives pagination links
      Given Order list_filter ['quantity'] and a page size of 1
      When  filter_quantity=3 is requested
      Then  the next-page link carries filter_quantity=3
    """
    # Given Order list_filter ['quantity'] and a page size of 1
    client = _client()

    # When filter_quantity=3 is requested
    resp = client.get("/admin/tforder?filter_quantity=3&page_size=1")

    # Then the next-page link carries filter_quantity=3
    assert "&filter_quantity=3" in resp.text


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def test_parse_filter_params_restricts_operators() -> None:
    """
    Scenario: parse_filter_params honours an operator whitelist
      Given ops={'exact'}
      When  filter_quantity=3 and filter_quantity__gte=1 are parsed
      Then  only the exact condition is returned
    """
    # Given ops={'exact'}
    params = {"filter_quantity": "3", "filter_quantity__gte": "1"}

    # When filter_quantity=3 and filter_quantity__gte=1 are parsed
    parsed = parse_filter_params(TfOrder, params, ["quantity"], ops={"exact"})

    # Then only the exact condition is returned
    assert parsed.conditions == [FilterCondition("quantity", "exact", 3)]
    assert parsed.active == {"quantity": "3"}


def test_parse_filter_params_accepts_every_operator_by_default() -> None:
    """
    Scenario: without an operator whitelist every operator is parsed
      Given no ops argument
      When  filter_quantity__gte=1 is parsed
      Then  a gte condition is returned
    """
    # Given no ops argument
    params = {"filter_quantity__gte": "1"}

    # When filter_quantity__gte=1 is parsed
    parsed = parse_filter_params(TfOrder, params, ["quantity"])

    # Then a gte condition is returned
    assert parsed.conditions == [FilterCondition("quantity", "gte", 1)]


def test_request_tz_without_a_request_returns_the_default() -> None:
    """
    Scenario: request_tz falls back to the default without a request
      Given no request and a non-tzinfo default
      When  request_tz runs
      Then  UTC is returned
    """
    # Given no request and a non-tzinfo default
    # When request_tz runs
    result = request_tz(None, None)

    # Then UTC is returned
    assert result is timezone.utc
