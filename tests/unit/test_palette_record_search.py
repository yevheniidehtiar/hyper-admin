"""Record search in the command palette (st-v059-nav-05).

Spec: ``docs/specs/navigation-and-list-ux.md`` (Addendum: record search). A real
admin is mounted at ``/admin`` over SQLite, with the host's bearer-token user
(``ExternalAuth``) and a permission function, so the endpoint runs through the
admin's own route class, permission checks and ``get_queryset`` scoping.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.palette_search import (
    MAX_QUERY_LENGTH,
    MODELS_PER_REQUEST,
    RESULTS_PER_MODEL,
    PaletteSearch,
    PaletteSource,
)


class PsOrder(SQLModel, table=True):
    __tablename__ = "ps_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""
    owner_id: int = 1

    def __str__(self) -> str:
        return self.number


class PsInvoice(SQLModel, table=True):
    __tablename__ = "ps_invoice"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class PsNote(SQLModel, table=True):
    __tablename__ = "ps_note"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class PsLog(SQLModel, table=True):
    __tablename__ = "ps_log"

    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class PsOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    nav_group = "Sales"
    icon = "receipt"

    def get_queryset(self, request: Any = None) -> dict[str, Any]:
        """Each user sees only their own orders."""
        user = getattr(getattr(request, "state", None), "user", None)
        return {"owner_id": user.id} if user is not None else {}


class PsAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def _admin() -> type[PsAdmin]:
    """A fresh admin class: ``site.register(options=...)`` sets options on the class."""
    return type("PsModelAdmin", (PsAdmin,), {})


USERS = {
    "ada": SimpleNamespace(id=1, username="ada", is_staff=True),
    "bo": SimpleNamespace(id=2, username="bo", is_staff=True),
}


def get_current_user(authorization: str | None = Header(default=None)) -> Any:
    """The host's ``get_user``: ``Bearer <name>``."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return USERS.get(authorization.removeprefix("Bearer "))


def _bearer(name: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {name}"}


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


@pytest.fixture
def engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'palette.db'}")

    async def _seed() -> None:
        tables = [m.__table__ for m in (PsOrder, PsInvoice, PsNote, PsLog)]  # type: ignore[attr-defined]
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=tables)
        async with AsyncSession(engine) as session:
            session.add(PsOrder(id=1042, number="ORD-1042", owner_id=1))
            session.add(PsOrder(id=2042, number="ORD-2042", owner_id=2))
            for n in range(10):
                session.add(PsOrder(id=3000 + n, number=f"BULK-{n}", owner_id=1))
            session.add(PsInvoice(id=1, number="INV-1042"))
            session.add(PsNote(id=1, number="NOTE-1042"))
            session.add(PsLog(id=1, number="LOG-1042"))
            await session.commit()

    anyio.run(_seed)
    return engine


def _build(engine: AsyncEngine, denied: frozenset[str] = frozenset()) -> tuple[Admin, TestClient]:
    """Orders (opted in), invoices (not), notes (opted in, no search fields), logs
    (opted in, no detail or edit page). ``denied`` codenames are refused."""
    site.register(PsOrder, PsOrderAdmin, options=AdminOptions(palette_search=True))
    site.register(PsInvoice, _admin())
    site.register(PsNote, _admin(), options=AdminOptions(palette_search=True, search_fields=[]))
    site.register(
        PsLog,
        _admin(),
        options=AdminOptions(palette_search=True, can_edit=False, can_detail=False),
    )
    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(
            secret_key="palette-search-secret", csrf_mode="off", plugins_enabled=False
        ),
        auth=ExternalAuth(
            get_user=get_current_user, has_permission=lambda user, code: code not in denied
        ),
    )
    admin.mount("/admin")
    return admin, TestClient(app, follow_redirects=False)


def _search(client: TestClient, q: str, user: str = "ada") -> Any:
    response = client.get("/admin/nav/search", params={"q": q}, headers=_bearer(user))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["groups"]


@pytest.fixture
def listed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Table names every adapter ``list`` call ran against."""
    calls: list[str] = []
    original = SQLModelAdapter.list

    async def spy(self: SQLModelAdapter, *args: Any, **kwargs: Any) -> Any:
        calls.append(self.model.__tablename__)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(SQLModelAdapter, "list", spy)
    return calls


def test_records_of_opted_in_models_appear_in_the_palette(engine: AsyncEngine) -> None:
    """
    Scenario: records of opted-in models appear in the palette
      Given OrderAdmin(palette_search=True) and order "ORD-1042"
      When  the user types "1042" in the palette
      Then  "ORD-1042" is listed under Orders, opening its edit page
    """
    _, client = _build(engine)

    groups = _search(client, "1042")

    assert groups == [
        {
            "key": "psorder",
            "label": "Ps orders",
            "items": [{"label": "ORD-1042", "url": "/admin/psorder/1042/edit"}],
        }
    ]


def test_models_without_opt_in_are_never_queried(engine: AsyncEngine, listed: list[str]) -> None:
    """
    Scenario: models without opt-in are never queried
      Given InvoiceAdmin without palette_search, and invoice "INV-1042"
      When  the user types "1042"
      Then  no query runs against the invoice table and no invoice is listed
      And   opted-in models without search fields or without a page to open are skipped too
    """
    _, client = _build(engine)

    groups = _search(client, "1042")

    assert listed == ["ps_order"]
    assert [group["key"] for group in groups] == ["psorder"]


def test_records_of_a_model_the_user_may_not_view_are_never_queried(
    engine: AsyncEngine, listed: list[str]
) -> None:
    """
    Scenario: the user lacks view_<model>
      Given the user lacks view_psorder
      When  the user types "1042"
      Then  no order is listed and the order table is not queried
    """
    _, client = _build(engine, frozenset({"view_psorder"}))

    assert _search(client, "1042") == []
    assert listed == []


def test_a_read_only_user_opens_the_detail_page(engine: AsyncEngine) -> None:
    """
    Scenario: a found record opens the page the user may use
      Given the user holds view_psorder but not change_psorder
      When  the user types "1042"
      Then  "ORD-1042" opens its detail page
    """
    _, client = _build(engine, frozenset({"change_psorder"}))

    groups = _search(client, "1042")

    assert groups[0]["items"] == [{"label": "ORD-1042", "url": "/admin/psorder/1042"}]


def test_get_queryset_scopes_the_records(engine: AsyncEngine) -> None:
    """
    Scenario: get_queryset scopes the palette like the list
      Given orders "ORD-1042" (owned by ada) and "ORD-2042" (owned by bo)
      When  each user types "042"
      Then  each sees only their own order
    """
    _, client = _build(engine)

    ada = _search(client, "042", "ada")
    bo = _search(client, "042", "bo")

    assert [item["label"] for item in ada[0]["items"]] == ["ORD-1042"]
    assert [item["label"] for item in bo[0]["items"]] == ["ORD-2042"]


def test_results_per_model_are_capped(engine: AsyncEngine) -> None:
    """
    Scenario: at most N results per model
      Given ten orders numbered "BULK-0" to "BULK-9"
      When  the user types "bulk"
      Then  only the first RESULTS_PER_MODEL are returned
    """
    _, client = _build(engine)

    items = _search(client, "bulk")[0]["items"]

    assert [item["label"] for item in items] == [f"BULK-{n}" for n in range(RESULTS_PER_MODEL)]


def test_short_and_long_queries(engine: AsyncEngine, listed: list[str]) -> None:
    """
    Scenario: a one-character query touches no table, an over-long one is refused
      Given the admin with opted-in orders
      When  the user sends "1" (after trimming), then MAX_QUERY_LENGTH + 1 characters
      Then  the first returns no groups without a query, the second is a 422
    """
    _, client = _build(engine)

    assert _search(client, " 1 ") == []
    assert listed == []
    long = client.get(
        "/admin/nav/search", params={"q": "x" * (MAX_QUERY_LENGTH + 1)}, headers=_bearer("ada")
    )
    assert long.status_code == 422


def test_a_database_error_returns_no_records(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: one broken table never breaks the palette
      Given the order table query fails
      When  the user types "1042"
      Then  the response is 200 with no groups, and the error is logged
    """
    _, client = _build(engine)

    async def broken(self: SQLModelAdapter, *args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT", {}, Exception("no such table"))

    monkeypatch.setattr(SQLModelAdapter, "list", broken)

    assert _search(client, "1042") == []
    assert "Palette search on PsOrder failed" in caplog.text


def test_the_route_is_absent_when_no_model_opts_in(tmp_path: Path) -> None:
    """
    Scenario: no opt-in, no endpoint
      Given no registered model sets palette_search
      When  /admin/nav/search is requested
      Then  it is a 404, and no model is marked searchable
    """
    site.register(PsInvoice, _admin())
    app = FastAPI()
    admin = Admin(
        app,
        engine=create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'none.db'}"),
        settings=HyperAdminSettings(
            secret_key="palette-search-secret", csrf_mode="off", plugins_enabled=False
        ),
    )
    admin.mount("/admin")

    response = TestClient(app).get("/admin/nav/search", params={"q": "1042"})

    assert response.status_code == 404, response.text[:300]
    assert admin.templates.env.globals["palette_search_models"] == frozenset()


class _FakeView:
    """A view whose ``palette_records`` returns ``result`` and counts calls."""

    def __init__(self, result: list[dict[str, str]] | None) -> None:
        self.result = result
        self.calls = 0

    async def palette_records(self, request: Any, query: str, limit: int) -> Any:
        self.calls += 1
        return self.result


def test_models_per_request_are_capped() -> None:
    """
    Scenario: at most M models per request
      Given two skipped models, then MODELS_PER_REQUEST + 2 queried models without matches
      When  a search runs
      Then  the skipped models do not count, and the last two are never asked
    """
    search = PaletteSearch()
    skipped = [_FakeView(None), _FakeView(None)]
    queried = [_FakeView([]) for _ in range(MODELS_PER_REQUEST + 2)]
    for n, view in enumerate(skipped + queried):
        search.add(PaletteSource(key=f"m{n}", label=f"M{n}", view=view))

    response = anyio.run(search.search, SimpleNamespace(), "query")

    assert json.loads(response.body) == {"groups": []}
    assert [view.calls for view in skipped] == [1, 1]
    assert [view.calls for view in queried] == [1] * MODELS_PER_REQUEST + [0, 0]
    assert search.keys == frozenset(f"m{n}" for n in range(len(skipped + queried)))


def _island(admin: Admin, **state: Any) -> dict[str, Any]:
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/admin/psorder",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "app": admin.app,
    }
    request = Request(scope)
    request.state.user = USERS["ada"]
    for key, value in state.items():
        setattr(request.state, key, value)
    template = admin.templates.env.get_template("components/command_palette.html")
    html = template.render(request=request, admin_prefix="/admin", auth_enabled=True)
    match = re.search(r'id="ha-nav-data">(.*?)</script>', html)
    assert match is not None
    return {"data": json.loads(match.group(1)), "html": html}


def test_the_island_offers_record_search_only_with_a_visible_opted_in_model(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: the palette knows where to search only when it may
      Given orders opt in to palette search
      When  the palette renders for a user who may view orders, then for one who may not
      Then  the first island has the search url and a "records" placeholder
      And   the second has no search url and the plain placeholder
    """
    admin, _ = _build(engine)

    allowed = _island(admin)
    hidden = _island(admin, user_permissions=frozenset({"view_psinvoice"}))

    assert allowed["data"]["search_url"] == "/admin/nav/search"
    assert "Search models, pages and records" in allowed["html"]
    assert hidden["data"]["search_url"] is None
    assert "Search models and pages…" in hidden["html"]
