"""The list view pages by keyset cursor when the model opts in (SDD adapter-query-performance A4)."""

import warnings
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import KeysetFallbackWarning, decode_cursor, encode_cursor
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

ROWS = 25
PAGE_SIZE = 10
LIST_URL = "/admin/cpitem"


class CpItem(SQLModel, table=True):
    __tablename__ = "test_cp_item"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    score: int | None = None


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


async def _seed_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        for i in range(1, ROWS + 1):
            # Row 1 has no score, so a keyset over ``score`` must fall back to OFFSET.
            session.add(CpItem(id=i, name=f"item {i:02d}", score=None if i == 1 else i))
        await session.commit()
    return engine


def _client(**options: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=anyio.run(_seed_engine),
        settings=HyperAdminSettings(create_tables=False),
    )
    site.register(
        CpItem,
        type(
            "CpItemAdmin",
            (ModelAdmin,),
            {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def _ids(response: Any) -> list[int]:
    return [row["_pk"] for row in response.context["items"]]


def test_offset_mode_keeps_page_numbers_and_total() -> None:
    """
    Scenario: pagination_mode="offset" preserves current behaviour
      Given a model with the default pagination_mode and 25 rows
      When  GET the list with page=2 and page_size=10
      Then  rows 11 to 20 are listed with the exact total and page count
      And   the pagination context has has_next/has_prev and no cursors
    """
    response = _client().get(LIST_URL, params={"page": 2, "page_size": PAGE_SIZE})

    assert response.status_code == 200
    assert _ids(response) == list(range(11, 21))
    pagination = response.context["pagination"]
    assert pagination["mode"] == "offset"
    assert pagination["total_items"] == ROWS
    assert pagination["total_pages"] == 3
    assert (pagination["start_index"], pagination["end_index"]) == (11, 20)
    assert pagination["has_next"] is True
    assert pagination["has_prev"] is True
    assert pagination["next_cursor"] is None
    assert pagination["prev_cursor"] is None
    assert f"of {ROWS} results" in response.text


def test_offset_mode_last_page_has_no_next() -> None:
    """
    Scenario: the last offset page has no next page
      Given a model with the default pagination_mode and 25 rows
      When  GET the list with page=3 and page_size=10
      Then  rows 21 to 25 are listed with has_next False
    """
    response = _client().get(LIST_URL, params={"page": 3, "page_size": PAGE_SIZE})

    assert _ids(response) == list(range(21, ROWS + 1))
    assert response.context["pagination"]["has_next"] is False


def test_offset_mode_ignores_a_cursor_param() -> None:
    """
    Scenario: a cursor in the URL does not change an offset-mode list
      Given a model with the default pagination_mode
      When  GET the list with a cursor and no page
      Then  the first page is listed as if no cursor were given
    """
    cursor = encode_cursor(10, 10, "next")

    response = _client().get(LIST_URL, params={"cursor": cursor, "page_size": PAGE_SIZE})

    assert response.status_code == 200
    assert _ids(response) == list(range(1, 11))
    assert response.context["pagination"]["has_prev"] is False


def test_cursor_mode_first_page_has_next_cursor_and_no_total() -> None:
    """
    Scenario: pagination_mode="cursor" uses keyset on (sort_col, pk)
      Given AdminOptions(pagination_mode="cursor") and 25 rows
      When  GET the list without a cursor
      Then  the first 10 rows are listed
      And   the pagination context has total None, has_next and a next_cursor
    """
    response = _client(pagination_mode="cursor").get(LIST_URL, params={"page_size": PAGE_SIZE})

    assert response.status_code == 200
    assert _ids(response) == list(range(1, 11))
    pagination = response.context["pagination"]
    assert pagination["mode"] == "cursor"
    assert pagination["total_items"] is None
    assert pagination["has_next"] is True
    assert pagination["has_prev"] is False
    assert pagination["next_cursor"] is not None
    assert decode_cursor(pagination["next_cursor"]).direction == "next"
    assert pagination["cursor"] is None


def test_cursor_mode_next_cursor_continues_the_previous_page() -> None:
    """
    Scenario: cursor decodes to (pk, sort_col, direction)
      Given a first cursor-mode page returned a next_cursor
      When  GET the list with cursor=next_cursor
      Then  rows 11 to 20 are listed, contiguous with the first page
      And   the page has a prev_cursor that leads back to rows 1 to 10
    """
    client = _client(pagination_mode="cursor")
    first = client.get(LIST_URL, params={"page_size": PAGE_SIZE}).context["pagination"]

    second = client.get(LIST_URL, params={"page_size": PAGE_SIZE, "cursor": first["next_cursor"]})

    assert second.status_code == 200
    assert _ids(second) == list(range(11, 21))
    pagination = second.context["pagination"]
    assert pagination["has_prev"] is True
    assert pagination["has_next"] is True
    assert pagination["cursor"] == first["next_cursor"]
    back = client.get(
        LIST_URL, params={"page_size": PAGE_SIZE, "cursor": pagination["prev_cursor"]}
    )
    assert _ids(back) == list(range(1, 11))


def test_cursor_mode_last_page_has_no_next() -> None:
    """
    Scenario: the last cursor page has no next link
      Given a cursor pointing after row 20 of 25
      When  GET the list with that cursor
      Then  rows 21 to 25 are listed with has_next False and no next_cursor
    """
    cursor = encode_cursor(20, 20, "next")

    response = _client(pagination_mode="cursor").get(
        LIST_URL, params={"page_size": PAGE_SIZE, "cursor": cursor}
    )

    assert _ids(response) == list(range(21, ROWS + 1))
    pagination = response.context["pagination"]
    assert pagination["has_next"] is False
    assert pagination["next_cursor"] is None


def test_cursor_mode_rejects_a_tampered_cursor_with_400() -> None:
    """
    Scenario: invalid/tampered cursor returns 400
      Given AdminOptions(pagination_mode="cursor")
      When  GET the list with cursor=not-base64
      Then  the response is 400 with "Invalid pagination cursor"
    """
    response = _client(pagination_mode="cursor").get(LIST_URL, params={"cursor": "not-base64"})

    assert response.status_code == 400
    assert "Invalid pagination cursor" in response.text


def test_cursor_mode_falls_back_to_page_numbers_on_a_sort_with_nulls() -> None:
    """
    Scenario: cursor mode falls back to offset when sort is non-deterministic
      Given AdminOptions(pagination_mode="cursor") and a sort column holding a NULL
      When  GET the list sorted by that column with page=2
      Then  a KeysetFallbackWarning is emitted
      And   the page is served by page number with an exact total
    """
    client = _client(pagination_mode="cursor")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        response = client.get(
            LIST_URL, params={"page": 2, "page_size": PAGE_SIZE, "sort_by": "score"}
        )

    assert response.status_code == 200
    assert any(issubclass(w.category, KeysetFallbackWarning) for w in caught)
    pagination = response.context["pagination"]
    assert pagination["mode"] == "offset"
    assert pagination["page"] == 2
    assert pagination["total_items"] == ROWS
    assert pagination["has_prev"] is True
    assert pagination["next_cursor"] is None
