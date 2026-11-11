"""The pagination component renders cursor links in keyset mode (SDD adapter-query-performance A4, #230)."""

import html
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import KeysetFallbackWarning
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

ROWS = 25
PAGE_SIZE = 10
LIST_URL = "/admin/pgtplitem"


class PgTplItem(SQLModel, table=True):
    __tablename__ = "test_pg_tpl_item"
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
            # Row 1 has no score, so a keyset over ``score`` falls back to OFFSET.
            session.add(PgTplItem(id=i, name=f"item {i:02d}", score=None if i == 1 else i))
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
        PgTplItem,
        type(
            "PgTplItemAdmin",
            (ModelAdmin,),
            {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def _link(text: str, testid: str) -> str | None:
    """The opening ``<a>`` tag carrying ``data-testid=testid``, or ``None``."""
    match = re.search(rf'<a\b[^>]*data-testid="{testid}"[^>]*>', text)
    return match.group(0) if match else None


def _attr(tag: str, name: str) -> str:
    match = re.search(rf'\s{name}="([^"]*)"', tag)
    assert match, f"{name} missing on {tag}"
    return html.unescape(match.group(1))


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


def test_cursor_mode_next_link_carries_the_next_cursor() -> None:
    """
    Scenario: cursor mode renders a next link with the cursor instead of a page number
      Given AdminOptions(pagination_mode="cursor") and 25 rows
      When  GET the first list page
      Then  the next link's href and hx-get carry cursor=<next_cursor>
      And   neither carries a page number
      And   no previous link is rendered
    """
    # Given
    client = _client(pagination_mode="cursor")

    # When
    response = client.get(LIST_URL, params={"page_size": PAGE_SIZE})

    # Then
    next_cursor = response.context["pagination"]["next_cursor"]
    tag = _link(response.text, "pagination-next")
    assert tag is not None
    for attr in ("href", "hx-get"):
        query = _query(_attr(tag, attr))
        assert query["cursor"] == [next_cursor]
        assert "page" not in query
        assert query["page_size"] == [str(PAGE_SIZE)]
    assert _link(response.text, "pagination-prev") is None


def test_cursor_mode_prev_link_follows_the_prev_cursor() -> None:
    """
    Scenario: the previous link on a cursor page leads back to the earlier page
      Given a cursor-mode list on its second page
      When  the previous link's hx-get is followed
      Then  rows 1 to 10 are listed
    """
    # Given
    client = _client(pagination_mode="cursor")
    first = client.get(LIST_URL, params={"page_size": PAGE_SIZE})
    second = client.get(_attr(_link(first.text, "pagination-next") or "", "hx-get"))
    assert [row["_pk"] for row in second.context["items"]] == list(range(11, 21))

    # When
    prev_tag = _link(second.text, "pagination-prev")
    assert prev_tag is not None
    back = client.get(_attr(prev_tag, "hx-get"))

    # Then
    assert _query(_attr(prev_tag, "href"))["cursor"] == [
        second.context["pagination"]["prev_cursor"]
    ]
    assert [row["_pk"] for row in back.context["items"]] == list(range(1, 11))


def test_cursor_mode_hides_the_total_and_page_count() -> None:
    """
    Scenario: cursor mode hides the "X of Y" label
      Given AdminOptions(pagination_mode="cursor")
      When  GET the first list page
      Then  no "of N results" and no "Page N of M" label is rendered
    """
    # Given
    client = _client(pagination_mode="cursor")

    # When
    response = client.get(LIST_URL, params={"page_size": PAGE_SIZE})

    # Then
    assert not re.search(r"Showing \d+ to \d+ of", response.text)
    assert " of None " not in response.text
    assert not re.search(r"Page \d+ of \d+", response.text)
    assert 'data-testid="pagination-page"' not in response.text


def test_cursor_mode_last_page_has_no_next_link() -> None:
    """
    Scenario: the last cursor page renders no next link
      Given a cursor-mode list paged to rows 21 to 25
      When  the page is rendered
      Then  there is no next link and there is a previous link
    """
    # Given
    client = _client(pagination_mode="cursor")
    url: str | None = f"{LIST_URL}?page_size={PAGE_SIZE}"
    last: Any = None

    # When
    while url is not None:
        last = client.get(url)
        tag = _link(last.text, "pagination-next")
        url = _attr(tag, "hx-get") if tag else None

    # Then
    assert [row["_pk"] for row in last.context["items"]] == list(range(21, ROWS + 1))
    assert _link(last.text, "pagination-prev") is not None


def test_cursor_links_have_aria_labels() -> None:
    """
    Scenario: prev/next cursor links are labelled for assistive technology
      Given a cursor-mode list on its second page
      When  the page is rendered
      Then  the previous link has aria-label "Previous page"
      And   the next link has aria-label "Next page"
    """
    # Given
    client = _client(pagination_mode="cursor")
    first = client.get(LIST_URL, params={"page_size": PAGE_SIZE})

    # When
    second = client.get(_attr(_link(first.text, "pagination-next") or "", "hx-get"))

    # Then
    assert _attr(_link(second.text, "pagination-prev") or "", "aria-label") == "Previous page"
    assert _attr(_link(second.text, "pagination-next") or "", "aria-label") == "Next page"


def test_cursor_links_keep_search_sort_and_page_size() -> None:
    """
    Scenario: cursor links keep the list's search and sort
      Given a cursor-mode list searched for "item" and sorted by name descending
      When  the first page is rendered
      Then  the next link keeps search, sort_by, sort_direction and page_size
    """
    # Given
    client = _client(pagination_mode="cursor", search_fields=["name"])

    # When
    response = client.get(
        LIST_URL,
        params={
            "page_size": PAGE_SIZE,
            "search": "item",
            "sort_by": "name",
            "sort_direction": "desc",
        },
    )

    # Then
    query = _query(_attr(_link(response.text, "pagination-next") or "", "hx-get"))
    assert query["search"] == ["item"]
    assert query["sort_by"] == ["name"]
    assert query["sort_direction"] == ["desc"]
    assert query["page_size"] == [str(PAGE_SIZE)]


def test_offset_mode_pager_is_unchanged() -> None:
    """
    Scenario: pagination_mode="offset" keeps page-numbered links
      Given the default pagination_mode and 25 rows
      When  GET page 2
      Then  prev/next links carry page=1 and page=3 and no cursor
      And   the "of 25 results" and "Page 2 of 3" labels are shown
    """
    # Given
    client = _client()

    # When
    response = client.get(LIST_URL, params={"page": 2, "page_size": PAGE_SIZE})

    # Then
    prev_query = _query(_attr(_link(response.text, "pagination-prev") or "", "hx-get"))
    next_query = _query(_attr(_link(response.text, "pagination-next") or "", "hx-get"))
    assert prev_query["page"] == ["1"]
    assert next_query["page"] == ["3"]
    assert "cursor" not in prev_query
    assert "cursor" not in next_query
    assert f"of {ROWS} results" in response.text
    assert "Page 2 of 3" in response.text


def test_cursor_mode_fallback_keeps_page_numbers() -> None:
    """
    Scenario: a cursor-mode list served by OFFSET renders the page-numbered pager
      Given AdminOptions(pagination_mode="cursor") and a sort column holding a NULL
      When  GET page 2 sorted by that column
      Then  the next link carries page=3 and no cursor
    """
    # Given
    client = _client(pagination_mode="cursor")

    # When
    with pytest.warns(KeysetFallbackWarning):
        response = client.get(
            LIST_URL, params={"page": 2, "page_size": PAGE_SIZE, "sort_by": "score"}
        )

    # Then
    query = _query(_attr(_link(response.text, "pagination-next") or "", "hx-get"))
    assert query["page"] == ["3"]
    assert "cursor" not in query
    assert "Page 2 of 3" in response.text
