"""List-view filter pipeline, HTMX table-body swap and saved views (st-v056-fl-02).

Spec: ``docs/specs/filter-library.md``. The story's five scenarios run the
real routes through ``Admin.mount()`` on an in-memory SQLite database with a
stand-in auth backend, so ``HyperAdminRoute``, the CSRF guard and the
``request.state.user_key`` contract are all exercised:

  Scenario: HTMX list request returns tbody fragment with HX-Push-Url
  Scenario: POST /saved-views creates a row for the current user
  Scenario: GET /saved-views returns only the user's own rows
  Scenario: DELETE /saved-views/{id} fails for non-owner
  Scenario: CurrentPeriodDefault redirects on first load
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import anyio
import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.datastructures import QueryParams

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.filters import (
    BooleanFilter,
    CurrentPeriodDefault,
    DateRangeFilter,
    IsOwnerFilter,
    MultiChoiceFilter,
    MultiFKFilter,
    SavedView,
    SavedViewNameTakenError,
    SavedViewService,
    normalize_querystring,
    period_bounds,
)
from hyperadmin.views.dynamic import LIST_BODY_ID, DynamicModelView
from tests.conftest import with_csrf

SECRET = "x" * 40
HTMX = {"HX-Request": "true"}
BODY_TARGET = {"HX-Request": "true", "HX-Target": LIST_BODY_ID}
TABLE_TARGET = {"HX-Request": "true", "HX-Target": "model-list"}
JSON = {"accept": "application/json"}
HTML = {"accept": "text/html"}
LIST = "/admin/fvorder"
SAVED = "/admin/fvorder/saved-views"


class FvOrder(SQLModel, table=True):
    __tablename__ = "fv_order"
    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    status: str = "open"
    paid: bool = False
    created_by: int = 1
    created_at: date = date(2026, 1, 1)


ORDERS: list[dict[str, Any]] = [
    {"id": 1, "title": "o-alpha", "status": "open", "paid": False, "created_by": 1},
    {"id": 2, "title": "o-beta", "status": "late", "paid": True, "created_by": 2},
    {"id": 3, "title": "o-gamma", "status": "open", "paid": True, "created_by": 1},
]
# Rows 1 and 2 are early January, row 3 is "today" in UTC.
TODAY = datetime.now(timezone.utc).date()
CREATED = {1: date(2026, 1, 5), 2: date(2026, 1, 20), 3: TODAY}


@dataclass
class _User:
    id: int
    username: str
    is_superuser: bool = False


ALICE = _User(id=1, username="alice")
BOB = _User(id=2, username="bob")


class _Backend:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> _User:
        return self.user

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _AllowAll:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return True

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set()


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    site._registry = {}
    yield
    site._registry = {}


def _seed(engine: AsyncEngine, *, saved_view_table: bool = True) -> None:
    async def _setup() -> None:
        tables = [FvOrder.__table__]  # type: ignore[attr-defined]
        if saved_view_table:
            tables.append(SavedView.__table__)  # type: ignore[attr-defined]
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=tables)
        async with AsyncSession(engine) as session:
            session.add_all(
                [FvOrder(**row, created_at=CREATED[row["id"]]) for row in ORDERS]  # type: ignore[arg-type]
            )
            await session.commit()

    anyio.run(_setup)


def _client(
    *,
    list_filter: list[Any] | None = None,
    user: _User | None = ALICE,
    saved_views_enabled: bool = True,
    saved_view_table: bool = True,
) -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed(engine, saved_view_table=saved_view_table)
    app = FastAPI()
    settings = HyperAdminSettings(create_tables=False, secret_key=SECRET)
    if user is not None:
        admin = Admin(
            app=app,
            engine=engine,
            settings=settings,
            auth_backend=_Backend(user),
            permission_checker=_AllowAll(),
        )
    else:
        admin = Admin(app=app, engine=engine, settings=settings)
    options = AdminOptions(
        list_display=["title", "status"],
        list_filter=list_filter if list_filter is not None else [],
        saved_views_enabled=saved_views_enabled,
    )
    site.register(FvOrder, OrderAdmin, options=options)
    admin.mount(path="/admin")
    client = TestClient(app)
    client.headers["accept"] = "text/html"
    return with_csrf(client, SECRET), engine


def _titles(html: str) -> list[str]:
    return sorted({token for token in ("o-alpha", "o-beta", "o-gamma") if token in html})


def _ctx(resp: Any) -> dict[str, Any]:
    return resp.context  # type: ignore[attr-defined, no-any-return]


async def _rows(engine: AsyncEngine) -> list[SavedView]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(SavedView))).scalars().all())


async def _insert(engine: AsyncEngine, values: dict[str, Any]) -> int:
    async with AsyncSession(engine) as session:
        view = SavedView(**values)
        session.add(view)
        await session.commit()
        await session.refresh(view)
        assert view.id is not None
        return view.id


def _saved(engine: AsyncEngine, **values: Any) -> int:
    """Insert a SavedView row directly and return its id."""
    return anyio.run(_insert, engine, values)


# ---------------------------------------------------------------------------
# Scenario: HTMX list request returns tbody fragment with HX-Push-Url
# ---------------------------------------------------------------------------


def test_htmx_list_request_returns_tbody_fragment_with_push_url() -> None:
    """
    Scenario: HTMX list request returns tbody fragment with HX-Push-Url
      Given DateRangeFilter and request HX-Request: true
      When  GET /admin/fvorder?created_at__gte=2026-01-10
      Then  response body starts with "<tbody"
      And   HX-Push-Url header is "/admin/fvorder?created_at__gte=2026-01-10"
      And   only rows on or after that date are listed
    """
    # Given DateRangeFilter and request HX-Request: true
    client, _ = _client(list_filter=[DateRangeFilter(field="created_at")])

    # When GET /admin/fvorder?created_at__gte=2026-01-10
    resp = client.get(f"{LIST}?created_at__gte=2026-01-10", headers=HTMX)

    # Then response body starts with "<tbody" and HX-Push-Url carries the filter
    assert resp.status_code == 200
    assert resp.text.lstrip().startswith("<tbody")
    assert "<table" not in resp.text
    assert resp.headers["HX-Push-Url"] == f"{LIST}?created_at__gte=2026-01-10"
    assert _titles(resp.text) == ["o-beta", "o-gamma"]


def test_htmx_target_decides_between_table_and_body() -> None:
    """
    Scenario: HTMX target decides between the table and the body
      Given DateRangeFilter on the list
      When  an HTMX request targets the table wrapper (search, sort, pagination)
      Then  the whole table is returned, without HX-Push-Url
      When  an HTMX request targets the body (the sidebar)
      Then  only the tbody is returned
    """
    client, _ = _client(list_filter=[DateRangeFilter(field="created_at")])

    table = client.get(LIST, headers=TABLE_TARGET)
    assert table.text.lstrip().startswith('<div id="model-list"')
    assert "HX-Push-Url" not in table.headers

    body = client.get(LIST, headers=BODY_TARGET)
    assert body.text.lstrip().startswith("<tbody")
    assert body.headers["HX-Push-Url"] == LIST


def test_legacy_only_model_keeps_the_table_for_targetless_htmx_requests() -> None:
    """
    Scenario: legacy string list_filter keeps the pre-0.5.6 HTMX contract
      Given AdminOptions(list_filter=["status"])
      When  a target-less HTMX request lists the model
      Then  the full table component is returned
    """
    client, _ = _client(list_filter=["status"])

    resp = client.get(f"{LIST}?filter_status=late", headers=HTMX)

    assert resp.text.lstrip().startswith('<div id="model-list"')
    assert _titles(resp.text) == ["o-beta"]


def test_non_htmx_request_renders_full_page_with_filter_groups() -> None:
    """
    Scenario: non-HTMX request renders the full page
      Given DateRangeFilter, IsOwnerFilter, BooleanFilter and a legacy string
      When  the browser opens the filtered list
      Then  the full layout is rendered with the table
      And   every filter is rendered as a sidebar group, with chips for the applied ones
      And   pagination links keep the explicit filter pairs
    """
    client, _ = _client(
        list_filter=[
            DateRangeFilter(field="created_at"),
            IsOwnerFilter(owner_fields="created_by"),
            BooleanFilter(field="paid"),
            MultiChoiceFilter(field="status"),
            "status",
        ]
    )

    resp = client.get(f"{LIST}?created_at__gte=2026-01-01&page_size=1&filter_status=open")

    assert resp.status_code == 200
    assert "<table" in resp.text
    ctx = _ctx(resp)
    assert [g["slug"] for g in ctx["filter_groups"]] == [
        "created_at",
        "is_owner",
        "paid",
        "status",
        "status",
    ]
    assert 'data-testid="filter-created_at-gte"' in str(ctx["filter_groups"][0]["html"])
    assert "<select" in str(ctx["filter_groups"][4]["html"])
    assert ctx["applied_filters"][0]["slug"] == "created_at"
    assert ctx["applied_filters"][0]["value"] == "from 2026-01-01"
    assert ctx["filter_query"] == "&created_at__gte=2026-01-01"
    assert ctx["list_body_id"] == LIST_BODY_ID
    assert ctx["active_filters"] == {"status": "open"}
    assert (
        "page=2&search=&sort_by=id&sort_direction=asc&filter_status=open&created_at__gte=2026-01-01"
        in resp.text
    )


def test_legacy_string_list_filter_still_classifies_fields() -> None:
    """
    Scenario: legacy string list_filter still classifies fields
      Given AdminOptions(list_filter=["status", "paid"])
      When  the list view renders
      Then  filter_metadata carries the auto-classified boolean filter
      And   filter_status still narrows the rows
    """
    client, _ = _client(list_filter=["status", "paid"])

    resp = client.get(f"{LIST}?filter_paid=true")

    assert resp.status_code == 200
    assert _titles(resp.text) == ["o-beta", "o-gamma"]
    metadata = {entry["name"]: entry for entry in _ctx(resp)["filter_metadata"]}
    assert metadata["paid"]["type"] == "bool"
    assert _ctx(resp)["filter_errors"] == {}


def test_is_owner_filter_restricts_to_the_users_rows() -> None:
    """
    Scenario: IsOwnerFilter restricts to objects the user owns
      Given IsOwnerFilter(owner_fields="created_by") and the user is alice
      When  the request includes ?is_owner=1
      Then  the result rows all have created_by == alice's user key
    """
    client, _ = _client(list_filter=[IsOwnerFilter(owner_fields="created_by")])

    resp = client.get(f"{LIST}?is_owner=1", headers=BODY_TARGET)

    assert _titles(resp.text) == ["o-alpha", "o-gamma"]
    assert resp.headers["HX-Push-Url"] == f"{LIST}?is_owner=1"


# ---------------------------------------------------------------------------
# Scenario: CurrentPeriodDefault redirects on first load
# ---------------------------------------------------------------------------


def _month_query() -> str:
    start = period_bounds("month", TODAY)[0]
    return f"created_at__gte={start.isoformat()}&created_at__lte={TODAY.isoformat()}"


def test_current_period_default_redirects_on_first_load() -> None:
    """
    Scenario: CurrentPeriodDefault redirects on first load
      Given CurrentPeriodDefault(field="created_at", period="month") and no querystring
      When  GET /admin/fvorder
      Then  the browser is redirected to ?created_at__gte=<first of month>&created_at__lte=<today>
      And   the response includes HX-Push-Url with the same URL
      And   following it lists only this month's rows
    """
    client, _ = _client(
        list_filter=[
            DateRangeFilter(field="created_at"),
            CurrentPeriodDefault(field="created_at", period="month"),
        ]
    )

    resp = client.get(LIST, follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == f"{LIST}?{_month_query()}"
    assert resp.headers["HX-Push-Url"] == f"{LIST}?{_month_query()}"
    followed = client.get(resp.headers["location"])
    assert followed.status_code == 200
    assert _titles(followed.text) == ["o-gamma"]


def test_current_period_default_pushes_url_for_htmx_and_yields_to_user_input() -> None:
    """
    Scenario: CurrentPeriodDefault over HTMX, and once the user has chosen
      Given the same CurrentPeriodDefault
      When  an HTMX request has no querystring
      Then  the tbody is returned with HX-Push-Url carrying the default bounds
      When  the user picked dates or asked for ?created_at=all
      Then  no default is applied and nothing is redirected
    """
    client, _ = _client(
        list_filter=[
            DateRangeFilter(field="created_at"),
            CurrentPeriodDefault(field="created_at", period="month"),
        ]
    )

    htmx = client.get(f"{LIST}?page_size=5", headers=HTMX)
    assert htmx.status_code == 200
    assert htmx.text.lstrip().startswith("<tbody")
    assert htmx.headers["HX-Push-Url"] == f"{LIST}?page_size=5&{_month_query()}"
    assert _titles(htmx.text) == ["o-gamma"]

    chosen = client.get(f"{LIST}?created_at__lte=2026-01-10", follow_redirects=False)
    assert chosen.status_code == 200
    assert _titles(chosen.text) == ["o-alpha"]

    everything = client.get(f"{LIST}?created_at=all", follow_redirects=False)
    assert everything.status_code == 200
    assert _titles(everything.text) == ["o-alpha", "o-beta", "o-gamma"]


# ---------------------------------------------------------------------------
# Scenario: POST /saved-views creates a row for the current user
# ---------------------------------------------------------------------------


def test_post_saved_views_creates_a_row_for_the_current_user() -> None:
    """
    Scenario: POST /saved-views creates a row for the current user
      Given alice is authenticated
      When  POST /admin/fvorder/saved-views with name="Late this month" and querystring="?status=late"
      Then  a SavedView row exists with (user_key="1", model="fvorder", name="Late this month")
      And   the API client gets the view as 201 JSON with its href
    """
    client, engine = _client(list_filter=[DateRangeFilter(field="created_at")])

    resp = client.post(
        SAVED,
        data={"name": "Late this month", "querystring": "?status=late&page=3"},
        headers=JSON,
    )

    assert resp.status_code == 201, resp.text
    rows = anyio.run(_rows, engine)
    assert [(r.user_key, r.model, r.name, r.querystring) for r in rows] == [
        ("1", "fvorder", "Late this month", "status=late")
    ]
    assert resp.json()["href"] == f"{LIST}?status=late"
    assert resp.json()["name"] == "Late this month"
    assert resp.json()["is_default"] is False


def test_post_saved_views_sends_browsers_and_htmx_to_the_new_view() -> None:
    """
    Scenario: saving from the sidebar lands on the new view
      Given alice posts the save form from a filtered list (no querystring field)
      When  the request is a plain form post
      Then  it is answered with 303 to the list carrying the request's own querystring
      When  the request comes from HTMX
      Then  it is answered with 204 and HX-Redirect to that URL
    """
    client, _ = _client(list_filter=[DateRangeFilter(field="created_at")])

    form = client.post(
        f"{SAVED}?created_at__gte=2026-01-01", data={"name": "Jan"}, follow_redirects=False
    )
    assert form.status_code == 303
    assert form.headers["location"] == f"{LIST}?created_at__gte=2026-01-01"

    htmx = client.post(SAVED, data={"name": "Everything"}, headers=HTMX)
    assert htmx.status_code == 204
    assert htmx.headers["HX-Redirect"] == LIST


def test_post_saved_views_rejects_taken_and_blank_names() -> None:
    """
    Scenario: saved view name collision per user
      Given alice already has "Late"
      When  she saves another "Late" on the same model
      Then  the response is 409 and names the collision
      When  she posts a blank name
      Then  the response is 422
    """
    client, _ = _client(list_filter=[DateRangeFilter(field="created_at")])
    assert client.post(SAVED, data={"name": "Late"}, headers=JSON).status_code == 201

    taken = client.post(SAVED, data={"name": " Late "}, headers=JSON)
    assert taken.status_code == 409
    assert "already have a view called" in taken.json()["detail"]

    blank = client.post(SAVED, data={"name": "   "}, headers=JSON)
    assert blank.status_code == 422
    assert blank.json()["detail"] == "Give the view a name."


# ---------------------------------------------------------------------------
# Scenario: GET /saved-views returns only the user's own rows
# ---------------------------------------------------------------------------


def test_get_saved_views_returns_only_the_users_own_rows() -> None:
    """
    Scenario: GET /saved-views returns only the user's own rows
      Given alice has 2 saved views and bob has 1
      When  bob requests GET /admin/fvorder/saved-views
      Then  the response contains only bob's row
    """
    client, engine = _client(user=BOB)
    _saved(engine, user_key="1", model="fvorder", name="A1", querystring="status=open")
    _saved(engine, user_key="1", model="fvorder", name="A2", querystring="")
    bob_id = _saved(engine, user_key="2", model="fvorder", name="B1", querystring="status=late")

    resp = client.get(SAVED, headers=JSON)

    assert resp.status_code == 200
    assert [(v["id"], v["name"], v["href"]) for v in resp.json()["views"]] == [
        (bob_id, "B1", f"{LIST}?status=late")
    ]


def test_list_page_context_carries_the_saved_views_panel() -> None:
    """
    Scenario: the sidebar shows the user's views and marks the one matching the URL
      Given alice has two views and bob has one
      When  alice opens the list with the querystring of her first view (page 2 of it)
      Then  the context lists alice's views only, with delete URLs
      And   the matching view is active regardless of parameter order and page
    """
    client, engine = _client()
    a1 = _saved(engine, user_key="1", model="fvorder", name="A1", querystring="paid=1&status=open")
    _saved(engine, user_key="1", model="fvorder", name="A2", querystring="")
    _saved(engine, user_key="2", model="fvorder", name="B1", querystring="")

    resp = client.get(f"{LIST}?status=open&page=2&paid=1")

    ctx = _ctx(resp)
    assert ctx["saved_views_enabled"] is True
    assert ctx["saved_views_url"].endswith(SAVED)
    assert ctx["current_query"] == "paid=1&status=open"
    assert ctx["active_saved_view_id"] == a1
    assert [(v["name"], v["active"]) for v in ctx["saved_views"]] == [("A1", True), ("A2", False)]
    assert ctx["saved_views"][0]["delete_url"].endswith(f"{SAVED}/{a1}")
    assert ctx["saved_views"][1]["href"] == LIST


# ---------------------------------------------------------------------------
# Scenario: DELETE /saved-views/{id} fails for non-owner
# ---------------------------------------------------------------------------


def test_delete_saved_view_fails_for_non_owner() -> None:
    """
    Scenario: DELETE /saved-views/{id} fails for non-owner
      Given alice has saved view id=42
      When  bob issues DELETE /admin/fvorder/saved-views/42
      Then  response is 404 and the row is still there
    """
    client, engine = _client(user=BOB)
    _saved(engine, id=42, user_key="1", model="fvorder", name="Mine", querystring="")

    resp = client.delete(f"{SAVED}/42", headers=JSON)

    assert resp.status_code == 404
    assert len(anyio.run(_rows, engine)) == 1


def test_delete_saved_view_removes_the_owners_row() -> None:
    """
    Scenario: the owner deletes a view
      Given alice has two views
      When  she deletes one as an API client and the other over HTMX
      Then  the API delete is 204, the HTMX delete an empty 200, and both rows are gone
    """
    client, engine = _client()
    first = _saved(engine, user_key="1", model="fvorder", name="One", querystring="")
    second = _saved(engine, user_key="1", model="fvorder", name="Two", querystring="")

    assert client.delete(f"{SAVED}/{first}", headers=JSON).status_code == 204
    htmx = client.delete(f"{SAVED}/{second}", headers=HTMX)
    assert htmx.status_code == 200
    assert htmx.text == ""
    assert anyio.run(_rows, engine) == []


# ---------------------------------------------------------------------------
# Loading a saved view, and the switches that turn the feature off
# ---------------------------------------------------------------------------


def test_view_param_loads_the_saved_querystring() -> None:
    """
    Scenario: loading a saved view applies its querystring
      Given alice has a saved view "Open"
      When  alice opens ?view=<id>
      Then  she is redirected to the list with that view's querystring
      And   someone else's id, or a non-numeric one, is 404
    """
    client, engine = _client(list_filter=["status"])
    own = _saved(
        engine,
        user_key="1",
        model="fvorder",
        name="Open",
        querystring="filter_status=open",
    )
    other = _saved(engine, user_key="2", model="fvorder", name="B", querystring="")

    resp = client.get(f"{LIST}?view={own}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{LIST}?filter_status=open"
    assert _titles(client.get(resp.headers["location"]).text) == ["o-alpha", "o-gamma"]

    assert client.get(f"{LIST}?view={other}", follow_redirects=False).status_code == 404
    assert client.get(f"{LIST}?view=abc", follow_redirects=False).status_code == 404


def test_saved_views_disabled_leaves_endpoints_and_panel_out() -> None:
    """
    Scenario: saved_views_enabled=False
      Given AdminOptions(saved_views_enabled=False)
      When  the saved-view routes are requested and the list is opened with ?view=1
      Then  the routes do not exist and ?view= is ignored
      And   the list context reports the panel as disabled
    """
    client, _ = _client(saved_views_enabled=False)

    assert client.get(SAVED, headers=JSON).status_code == 404
    assert client.post(SAVED, data={"name": "x"}, headers=JSON).status_code in {404, 405}
    resp = client.get(f"{LIST}?view=1")
    assert resp.status_code == 200
    assert _ctx(resp)["saved_views_enabled"] is False
    assert _ctx(resp)["saved_views"] == []


def test_missing_saved_view_table_never_breaks_the_list_page(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: the host has not created hyperadmin_saved_view yet
      Given the table is missing
      When  the list page is opened
      Then  it renders with the saved-views panel left out and a warning naming the fix
      And   the saved-view endpoint itself fails loudly (a 500 the host sees)
    """
    client, _ = _client(saved_view_table=False)

    with caplog.at_level(logging.WARNING, logger="hyperadmin.views.dynamic"):
        resp = client.get(LIST)

    assert resp.status_code == 200
    assert _ctx(resp)["saved_views_enabled"] is False
    assert any("hyperadmin_saved_view" in record.message for record in caplog.records)
    client_without_raise = TestClient(client.app, raise_server_exceptions=False)
    with_csrf(client_without_raise, SECRET)
    assert client_without_raise.get(SAVED, headers=JSON).status_code == 500


def test_saved_views_need_a_signed_in_user() -> None:
    """
    Scenario: no auth configured
      Given an admin without an auth backend (no request.state.user_key)
      When  the saved-view endpoints are called and the list is opened
      Then  the endpoints answer 403 and the list hides the panel
    """
    client, _ = _client(user=None)

    assert client.get(SAVED, headers=JSON).status_code == 403
    resp = client.get(LIST)
    assert resp.status_code == 200
    assert _ctx(resp)["saved_views_enabled"] is False


def test_filters_on_unknown_or_sensitive_fields_render_no_groups() -> None:
    """
    Scenario: list_filter names nothing filterable
      Given list_filter with a field the model lacks and a MultiFKFilter on a plain column
      When  the list renders
      Then  the unknown string yields no group and the FK filter renders without choices
    """
    client, _ = _client(list_filter=["nope"])
    assert _ctx(client.get(LIST))["filter_groups"] == []

    site._registry = {}
    client, _ = _client(list_filter=[MultiFKFilter(field="created_by")])
    resp = client.get(f"{LIST}?created_by__in=2")
    assert [g["slug"] for g in _ctx(resp)["filter_groups"]] == ["created_by"]
    assert _titles(resp.text) == ["o-beta"]


def test_list_rows_show_file_names_and_related_display_names() -> None:
    """
    Scenario: list cells for file and relation columns
      Given a row whose file column holds an upload and whose relation column holds a model
      When  the rows are built
      Then  the file cell is the stored name and the relation cell its display name
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    view = DynamicModelView(
        adapter=SQLModelAdapter(FvOrder, engine),
        options=AdminOptions(),
        templates=MagicMock(spec=Jinja2Templates),
        app_label=None,
        column_list=["id", "title", "status"],
    )
    item = SimpleNamespace(
        id=7, title=SimpleNamespace(name="scan.pdf"), status=FvOrder(id=9, title="related")
    )

    rows = view._list_rows([item], file_fields={"title"})

    assert rows[0]["title"] == "scan.pdf"
    assert rows[0]["status"] == "related"
    assert rows[0]["_pk"] == 7


# ---------------------------------------------------------------------------
# AdminOptions
# ---------------------------------------------------------------------------


def test_list_filter_accepts_strings_and_filter_defs_only() -> None:
    """
    Scenario: list_filter widened to list[FilterDef | str]
      Given a mix of strings and FilterDef instances
      Then  AdminOptions accepts it and saved views default to enabled
      Given an entry that is neither
      Then  AdminOptions rejects it at construction
    """
    options = AdminOptions(list_filter=["status", DateRangeFilter(field="created_at")])

    assert options.saved_views_enabled is True
    assert options.list_filter is not None
    assert isinstance(options.list_filter[1], DateRangeFilter)
    with pytest.raises(ValidationError, match="field names or FilterDef instances"):
        AdminOptions(list_filter=[42])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# SavedViewService and normalize_querystring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ""),
        ("", ""),
        ("?status=late&page=2&view=7&empty=", "status=late"),
        ("b=2&a=1", "a=1&b=2"),
        ({"status": "open", "page": "3"}, "status=open"),
        ([("x", "1"), ("x", "0")], "x=0&x=1"),
        (QueryParams("created_at__gte=2026-01-01&page=9"), "created_at__gte=2026-01-01"),
    ],
)
def test_normalize_querystring(raw: Any, expected: str) -> None:
    assert normalize_querystring(raw) == expected


def test_saved_view_table_is_part_of_the_hyperadmin_metadata() -> None:
    """
    Scenario: hosts create the table through init-db or Alembic
      Given hyperadmin.auth.metadata() (what init-db and Alembic hosts use)
      Then  it holds hyperadmin_saved_view with the per-user unique constraint
    """
    import hyperadmin.auth

    table = hyperadmin.auth.metadata().tables["hyperadmin_saved_view"]

    assert {c.name for c in table.columns} == {
        "id",
        "user_key",
        "model",
        "name",
        "querystring",
        "is_default",
        "created_at",
    }
    unique = [c for c in table.constraints if c.name == "uq_hyperadmin_saved_view_name"]
    assert [c.name for c in unique[0].columns] == ["user_key", "model", "name"]


def test_service_requires_a_database_seam() -> None:
    with pytest.raises(ValueError, match="engine"):
        SavedViewService()


def test_service_create_list_get_delete_round_trip() -> None:
    """
    Scenario: the service scopes everything to the owner
      Given alice saved a view through a host session factory
      Then  she can list, get and delete it, and bob cannot see or delete it
      And   a name longer than the column is refused
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed(engine)

    async def _run() -> None:
        service = SavedViewService(session_factory=lambda: AsyncSession(engine))
        view = await service.create(1, "order", "Mine", QueryParams("page=2&status=open"))
        assert view.id is not None
        assert view.querystring == "status=open"
        assert [v.name for v in await service.list_for("1", "order")] == ["Mine"]
        assert await service.list_for("2", "order") == []
        assert await service.get(1, "order", view.id) is not None
        assert await service.get(2, "order", view.id) is None
        assert await service.get(1, "other", view.id) is None
        assert await service.delete(2, "order", view.id) is False
        assert await service.delete(1, "order", view.id) is True
        assert await service.delete(1, "order", view.id) is False
        with pytest.raises(ValueError, match="at most 255"):
            await service.create(1, "order", "n" * 256, "")

    anyio.run(_run)


def test_service_create_treats_a_lost_race_as_a_name_collision() -> None:
    """
    Scenario: two saves of the same name race past the pre-check
      Given the unique constraint rejects the second insert at commit
      Then  the service reports SavedViewNameTakenError rather than a bare IntegrityError
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed(engine)

    class _RacySession(AsyncSession):
        async def commit(self) -> None:
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

    @asynccontextmanager
    async def _factory() -> Any:
        async with _RacySession(engine) as session:
            yield session

    async def _run() -> None:
        service = SavedViewService(session_factory=_factory)
        with pytest.raises(SavedViewNameTakenError) as info:
            await service.create("1", "order", "Dup", "")
        assert info.value.name == "Dup"

    anyio.run(_run)
