"""list_view surfaces database errors instead of swallowing them (st-v058-byoa-43).

Spec: ``docs/specs/bring-your-own-app.md`` section D.2.

Before the fix ``list_view`` caught every exception and rendered an empty list,
so a missing table looked exactly like an empty one and nothing was logged.
"""

import logging
import re
from typing import Any
from unittest.mock import AsyncMock

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.dynamic import _is_missing_table_error


class LeGadget(SQLModel, table=True):
    __tablename__ = "list_error_gadget"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    weight: int = 0
    is_active: bool = True


class LeGadgetAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean() -> Any:
    site._registry = {}
    yield
    site._registry = {}


async def _seed(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, tables=[LeGadget.__table__])
        for gid, name, weight, active in [(1, "zed", 3, 1), (2, "amy", 1, 0), (3, "bob", 2, 1)]:
            await conn.execute(
                text(
                    "INSERT INTO list_error_gadget (id, name, weight, is_active) "
                    "VALUES (:id, :name, :weight, :active)"
                ),
                {"id": gid, "name": name, "weight": weight, "active": active},
            )


def _client(*, seed: bool = True, debug: bool = False) -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    if seed:
        anyio.run(_seed, engine)
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, debug=debug),
    )
    site.register(
        LeGadget,
        LeGadgetAdmin,
        options=AdminOptions(list_filter=["weight", "is_active"]),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def _banner(html: str) -> str:
    match = re.search(r'<div[^>]*data-testid="list-error".*?</div>', html, re.DOTALL)
    assert match, "list-error banner not rendered"
    return match.group(0)


def _names(html: str) -> list[str]:
    seen: list[str] = []
    for name in re.findall(r">(zed|amy|bob)<", html):
        if name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------------------
# DB error surfaced
# ---------------------------------------------------------------------------


def test_db_error_surfaced(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: DB error surfaced
      Given the model table is missing
      When  the list is opened
      Then  the list-error banner mentions migrations
      And   an ERROR log with a traceback is emitted
    """
    # Given the model table is missing
    client = _client(seed=False)

    # When the list is opened
    with caplog.at_level(logging.ERROR, logger="hyperadmin.views.dynamic"):
        resp = client.get("/admin/legadget")

    # Then the list-error banner mentions migrations
    assert resp.status_code == 500
    banner = _banner(resp.text)
    assert "migrations" in banner
    assert "<code>hyperadmin init-db</code>" in banner
    assert "`" not in banner
    # And an ERROR log with a traceback is emitted
    records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert records
    assert records[0].exc_info is not None
    assert isinstance(records[0].exc_info[1], OperationalError)


def test_htmx_partial_with_db_error_returns_200_with_banner() -> None:
    """
    Scenario: HTMX partial shows the banner with status 200
      Given the model table is missing
      When  the list is refreshed through HTMX
      Then  the response is 200 and contains the list-error banner
    """
    # Given the model table is missing
    client = _client(seed=False)

    # When the list is refreshed through HTMX
    resp = client.get("/admin/legadget", headers={"hx-request": "true"})

    # Then the response is 200 and contains the list-error banner
    assert resp.status_code == 200
    assert "migrations" in _banner(resp.text)


def test_other_db_error_shows_banner_without_migration_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a non-missing-table DB error shows a generic banner
      Given the adapter raises a SQLAlchemyError unrelated to a missing table
      When  the list is opened
      Then  the list-error banner is shown without the migration hint
    """
    # Given the adapter raises a SQLAlchemyError unrelated to a missing table
    client = _client()
    failing = AsyncMock(side_effect=SQLAlchemyError("deadlock detected"))
    monkeypatch.setattr(SQLModelAdapter, "list", failing)

    # When the list is opened
    resp = client.get("/admin/legadget")

    # Then the list-error banner is shown without the migration hint
    assert resp.status_code == 500
    banner = _banner(resp.text)
    assert "init-db" not in banner
    assert "deadlock" not in banner  # raw driver text is never shown to the user


def test_filter_metadata_is_not_queried_after_a_list_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a failed list does not query the database again for filters
      Given list_filter is configured and the database is unreachable
      When  the list is opened
      Then  the list-error banner is rendered instead of a bare 500
      And   the filter metadata is not built
    """
    # Given list_filter is configured and the database is unreachable
    client = _client()
    monkeypatch.setattr(
        SQLModelAdapter, "list", AsyncMock(side_effect=SQLAlchemyError("connection refused"))
    )
    metadata = AsyncMock(side_effect=SQLAlchemyError("connection refused"))
    monkeypatch.setattr("hyperadmin.views.dynamic.list_view.build_filter_metadata", metadata)
    monkeypatch.setattr("hyperadmin.views.dynamic.base.build_filter_metadata", metadata)

    # When the list is opened
    resp = client.get("/admin/legadget")

    # Then the list-error banner is rendered instead of a bare 500
    assert resp.status_code == 500
    assert "Check the server logs" in _banner(resp.text)
    # And the filter metadata is not built
    metadata.assert_not_called()


def test_healthy_list_renders_no_banner() -> None:
    """
    Scenario: no banner when the query succeeds
      Given a seeded table
      When  the list is opened
      Then  the rows are listed and no list-error banner is rendered
    """
    # Given a seeded table
    client = _client()

    # When the list is opened
    resp = client.get("/admin/legadget")

    # Then the rows are listed and no list-error banner is rendered
    assert resp.status_code == 200
    assert 'data-testid="list-error"' not in resp.text
    assert _names(resp.text) == ["zed", "amy", "bob"]


# ---------------------------------------------------------------------------
# debug re-raises / non-DB errors propagate
# ---------------------------------------------------------------------------


def test_debug_re_raises() -> None:
    """
    Scenario: debug re-raises
      Given settings.debug=True and a failing query
      When  the list is opened
      Then  the exception propagates
    """
    # Given settings.debug=True and a failing query
    client = _client(seed=False, debug=True)

    # When the list is opened / Then the exception propagates
    with pytest.raises(OperationalError):
        client.get("/admin/legadget")


def test_non_db_exception_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: a non-database exception is not swallowed
      Given the adapter raises a RuntimeError
      When  the list is opened
      Then  the exception propagates
    """
    # Given the adapter raises a RuntimeError
    client = _client()
    monkeypatch.setattr(SQLModelAdapter, "list", AsyncMock(side_effect=RuntimeError("bug")))

    # When the list is opened / Then the exception propagates
    with pytest.raises(RuntimeError, match="bug"):
        client.get("/admin/legadget")


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("(sqlite3.OperationalError) no such table: gadget", True),
        ('relation "gadget" does not exist', True),
        ("UndefinedTableError: relation gadget", True),
        ("deadlock detected", False),
        ('column "weight" does not exist', False),
        ("function lower(integer) does not exist", False),
        ('schema "tenant" does not exist', False),
    ],
)
def test_is_missing_table_error(message: str, expected: bool) -> None:
    """
    Scenario: missing-table errors are recognised across backends
      Given a database error message from SQLite or PostgreSQL
      When  it is classified
      Then  only missing-table messages get the migration hint
    """
    assert _is_missing_table_error(SQLAlchemyError(message)) is expected


# ---------------------------------------------------------------------------
# Review amendment: user input never becomes a 500
# ---------------------------------------------------------------------------


def test_unknown_sort_by_returns_200_with_the_default_sort() -> None:
    """
    Scenario: ?sort_by=nope returns 200 with the default sort
      Given a seeded table
      When  the list is opened with ?sort_by=nope
      Then  the response is 200 and rows are in the default (id) order
    """
    # Given a seeded table
    client = _client()

    # When the list is opened with ?sort_by=nope
    resp = client.get("/admin/legadget?sort_by=nope&sort_direction=desc")

    # Then the response is 200 and rows are in the default (id) order
    assert resp.status_code == 200
    assert 'data-testid="list-error"' not in resp.text
    assert _names(resp.text) == ["zed", "amy", "bob"]


@pytest.mark.parametrize(
    "query",
    [
        "filter_weight=abc",
        "filter_weight=99999999999999999999999",
        "filter_is_active=maybe",
    ],
)
def test_uncoercible_filter_value_is_dropped_not_a_500(query: str) -> None:
    """
    Scenario: an uncoercible filter value is dropped
      Given a seeded table with list_filter on weight and is_active
      When  the list is opened with a filter value that does not fit the column type
      Then  the response is 200, no error banner is shown and the filter is ignored
    """
    # Given a seeded table with list_filter on weight and is_active
    client = _client()

    # When the list is opened with a filter value that does not fit the column type
    resp = client.get(f"/admin/legadget?{query}")

    # Then the response is 200, no error banner is shown and the filter is ignored
    assert resp.status_code == 200
    assert 'data-testid="list-error"' not in resp.text
    assert _names(resp.text) == ["zed", "amy", "bob"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("filter_weight=2", ["bob"]),
        ("filter_is_active=false", ["amy"]),
        ("filter_is_active=true", ["zed", "bob"]),
    ],
)
def test_valid_filter_values_are_coerced_and_applied(query: str, expected: list[str]) -> None:
    """
    Scenario: a valid filter value is coerced to the column type
      Given a seeded table with list_filter on weight and is_active
      When  the list is opened with a well-formed filter
      Then  only the matching rows are listed
    """
    # Given a seeded table with list_filter on weight and is_active
    client = _client()

    # When the list is opened with a well-formed filter
    resp = client.get(f"/admin/legadget?{query}")

    # Then only the matching rows are listed
    assert resp.status_code == 200
    assert _names(resp.text) == expected


def test_huge_page_number_is_not_a_500() -> None:
    """
    Scenario: an out-of-range page number does not crash the list
      Given a seeded table
      When  the list is opened with a page number past the 64-bit range
      Then  the response is 200 with no rows and no error banner
    """
    # Given a seeded table
    client = _client()

    # When the list is opened with a page number past the 64-bit range
    resp = client.get("/admin/legadget?page=99999999999999999999")

    # Then the response is 200 with no rows and no error banner
    assert resp.status_code == 200
    assert 'data-testid="list-error"' not in resp.text
    assert _names(resp.text) == []
