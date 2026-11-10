"""Unit tests for keyset (cursor) pagination in ``SQLModelAdapter`` (story #226, SDD §A4).

These tests are written ahead of the implementation (TDD red). They pin the contract from
``docs/specs/adapter-query-performance.md`` §A4:

- ``BaseAdapter.pagination_mode`` (``"offset"`` default, ``"cursor"`` opt-in), set by the router
  from ``AdminOptions.pagination_mode`` like ``count_cache_ttl``;
- ``list_paginated(..., cursor=...)`` returning a ``ListResult`` with ``total=None`` in cursor mode;
- opaque cursors ``base64url(json({"k": [pk, sort_value], "d": "next" | "prev", "v": 1}))``;
- ``InvalidCursorError`` for malformed or future-version cursors;
- ``KeysetFallbackWarning`` and OFFSET fallback when the sort column holds NULLs.

Every test that needs the new API carries the ``pending`` marker: a strict ``xfail``. The story
that makes a test pass (#227 core contract, #228 SQLModelAdapter) removes the marker from it;
a strict xfail that starts passing fails the suite, so the marker cannot be forgotten.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core import adapters as core_adapters
from hyperadmin.core.options import AdminOptions

pending = pytest.mark.xfail(
    strict=True,
    reason="keyset pagination is implemented by #227 (core) and #228 (SQLModelAdapter)",
)

TOTAL_ROWS = 25
PAGE_SIZE = 10


class KeysetItem(SQLModel, table=True):
    """Model with a non-unique sort column and a nullable one."""

    __tablename__ = "test_keyset_pagination_item"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    rank: int = Field(index=True)
    score: int | None = None


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return eng


@pytest.fixture
def adapter(engine: AsyncEngine) -> SQLModelAdapter:
    return SQLModelAdapter(model=KeysetItem, engine=engine)


@pytest.fixture
def cursor_adapter(adapter: SQLModelAdapter) -> SQLModelAdapter:
    adapter.pagination_mode = "cursor"  # type: ignore[attr-defined]
    return adapter


@pytest.fixture
def statements(engine: AsyncEngine) -> Iterator[list[str]]:
    """Collect the SQL text of every statement the engine executes."""
    captured: list[str] = []

    def _capture(
        _conn: Any, _cursor: Any, statement: str, _params: Any, _context: Any, _many: bool
    ) -> None:
        captured.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _capture)
    yield captured
    event.remove(engine.sync_engine, "before_cursor_execute", _capture)


async def _seed(adapter: SQLModelAdapter, count: int = TOTAL_ROWS) -> None:
    """Create ``count`` rows; ``rank`` repeats every 3 rows, so ties need the pk tiebreaker."""
    for i in range(1, count + 1):
        await adapter.create({"name": f"item-{i:02d}", "rank": i % 3, "score": i})


def _ids(items: list[Any]) -> list[int]:
    return [item.id for item in items]


async def _walk(adapter: SQLModelAdapter, order_by: str | None) -> list[list[int]]:
    """Follow ``next_cursor`` from the first page until ``has_next`` is false."""
    pages: list[list[int]] = []
    cursor: str | None = None
    while True:
        result = await adapter.list_paginated(  # type: ignore[attr-defined]
            cursor=cursor, page_size=PAGE_SIZE, order_by=order_by
        )
        pages.append(_ids(result.items))
        if not result.has_next:
            assert result.next_cursor is None
            return pages
        cursor = result.next_cursor
        assert len(pages) <= TOTAL_ROWS, "cursor chain does not terminate"


def _forge_cursor(payload: dict[str, Any]) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return raw.rstrip("=")


# ---------------------------------------------------------------------------
# Scenario: pagination_mode="offset" preserves current behaviour
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_still_returns_items_and_total_tuple(adapter: SQLModelAdapter) -> None:
    """
    Scenario: offset list() keeps the (items, total) tuple
      Given 25 rows and an adapter in the default pagination mode
      When  list(page=2, page_size=10, order_by="id") is called
      Then  rows 11-20 are returned with total 25
    """
    # Given
    await _seed(adapter)

    # When
    items, total = await adapter.list(page=2, page_size=PAGE_SIZE, order_by="id")

    # Then
    assert _ids(items) == list(range(11, 21))
    assert total == TOTAL_ROWS


@pending
def test_admin_options_pagination_mode_defaults_to_offset() -> None:
    """
    Scenario: pagination_mode defaults to offset
      Given AdminOptions created without pagination_mode
      When  pagination_mode is read
      Then  it is "offset", and "cursor" is accepted when set explicitly
    """
    # Given / When
    default = AdminOptions()
    cursor = AdminOptions(pagination_mode="cursor")  # type: ignore[call-arg]

    # Then
    assert default.pagination_mode == "offset"  # type: ignore[attr-defined]
    assert cursor.pagination_mode == "cursor"  # type: ignore[attr-defined]


@pending
def test_admin_options_rejects_unknown_pagination_mode() -> None:
    """
    Scenario: an unknown pagination_mode is rejected
      Given AdminOptions(pagination_mode="keyset")
      When  the options are validated
      Then  a validation error is raised
    """
    # When / Then
    with pytest.raises(ValueError, match="pagination_mode"):
        AdminOptions(pagination_mode="keyset")  # type: ignore[call-arg]


@pending
@pytest.mark.anyio
async def test_offset_mode_list_paginated_uses_page_numbers(
    adapter: SQLModelAdapter, statements: list[str]
) -> None:
    """
    Scenario: pagination_mode="offset" preserves current behaviour
      Given 25 rows and pagination_mode="offset"
      When  list_paginated(page=2, page_size=10) is called
      Then  the SQL uses OFFSET
      And   the result has rows 11-20, total 25 and no cursors
    """
    # Given
    await _seed(adapter)
    adapter.pagination_mode = "offset"  # type: ignore[attr-defined]
    statements.clear()

    # When
    result = await adapter.list_paginated(  # type: ignore[attr-defined]
        page=2, page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert any("OFFSET" in sql.upper() for sql in statements)
    assert _ids(result.items) == list(range(11, 21))
    assert result.total == TOTAL_ROWS
    assert result.next_cursor is None
    assert result.prev_cursor is None


# ---------------------------------------------------------------------------
# Scenario: pagination_mode="cursor" uses keyset on (sort_col, pk)
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
async def test_first_page_in_cursor_mode_returns_next_cursor(
    cursor_adapter: SQLModelAdapter, statements: list[str]
) -> None:
    """
    Scenario: the first cursor page has a next cursor and no OFFSET
      Given 25 rows and pagination_mode="cursor"
      When  list_paginated(cursor=None, page_size=10, order_by="id") is called
      Then  rows 1-10 are returned without OFFSET in the SQL
      And   has_next is true, has_prev is false and next_cursor is set
      And   total is None
    """
    # Given
    await _seed(cursor_adapter)
    statements.clear()

    # When
    result = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=None, page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert not any("OFFSET" in sql.upper() for sql in statements)
    assert isinstance(result, core_adapters.ListResult)  # type: ignore[attr-defined]
    assert _ids(result.items) == list(range(1, 11))
    assert result.has_next is True
    assert result.has_prev is False
    assert isinstance(result.next_cursor, str)
    assert result.next_cursor
    assert result.total is None


@pending
@pytest.mark.anyio
async def test_after_cursor_returns_the_next_page(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: a next cursor returns the following page contiguously
      Given 25 rows and the next_cursor of the first page ordered by id
      When  list_paginated(cursor=next_cursor, page_size=10) is called
      Then  rows 11-20 are returned
      And   has_prev and has_next are both true
    """
    # Given
    await _seed(cursor_adapter)
    first = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )

    # When
    second = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=first.next_cursor, page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert _ids(second.items) == list(range(11, 21))
    assert second.has_prev is True
    assert second.has_next is True
    assert second.total is None


@pending
@pytest.mark.anyio
async def test_cursor_after_page_is_not_offset_dependent(
    cursor_adapter: SQLModelAdapter, statements: list[str]
) -> None:
    """
    Scenario: a cursor page filters on the key tuple instead of skipping rows
      Given 25 rows and the next_cursor of the first page
      When  the next page is fetched with that cursor
      Then  the SQL has no OFFSET
    """
    # Given
    await _seed(cursor_adapter)
    first = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )
    statements.clear()

    # When
    await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=first.next_cursor, page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert statements
    assert not any("OFFSET" in sql.upper() for sql in statements)


# ---------------------------------------------------------------------------
# Scenario: ordering by PK works with cursor
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
async def test_cursor_chain_ordered_by_pk_visits_every_row_once(
    cursor_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: following next cursors visits every row once
      Given 25 rows and pagination_mode="cursor"
      When  next_cursor is followed from the first page ordered by id
      Then  three pages of 10, 10 and 5 rows cover ids 1-25 in order
    """
    # Given
    await _seed(cursor_adapter)

    # When
    pages = await _walk(cursor_adapter, order_by="id")

    # Then
    assert [len(page) for page in pages] == [10, 10, 5]
    assert [pk for page in pages for pk in page] == list(range(1, TOTAL_ROWS + 1))


@pending
@pytest.mark.anyio
async def test_cursor_chain_ordered_by_pk_descending(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: a descending pk sort pages backwards through the ids
      Given 25 rows and pagination_mode="cursor"
      When  next_cursor is followed from the first page ordered by "-id"
      Then  the pages cover ids 25 down to 1 without gaps or duplicates
    """
    # Given
    await _seed(cursor_adapter)

    # When
    pages = await _walk(cursor_adapter, order_by="-id")

    # Then
    assert pages[0] == list(range(25, 15, -1))
    assert [pk for page in pages for pk in page] == list(range(TOTAL_ROWS, 0, -1))


@pending
@pytest.mark.anyio
async def test_cursor_without_order_by_sorts_by_pk(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: cursor mode with no explicit sort uses the primary key
      Given 25 rows and pagination_mode="cursor"
      When  next_cursor is followed with order_by=None
      Then  the pages cover ids 1-25 in ascending order
    """
    # Given
    await _seed(cursor_adapter)

    # When
    pages = await _walk(cursor_adapter, order_by=None)

    # Then
    assert [pk for page in pages for pk in page] == list(range(1, TOTAL_ROWS + 1))


# ---------------------------------------------------------------------------
# Scenario: non-unique sort columns use the pk as tiebreaker
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
@pytest.mark.parametrize("order_by", ["rank", "-rank"])
async def test_cursor_chain_on_non_unique_column_uses_pk_tiebreaker(
    cursor_adapter: SQLModelAdapter, order_by: str
) -> None:
    """
    Scenario: a non-unique sort column pages by (sort_col, pk)
      Given 25 rows whose rank repeats every 3 rows
      When  next_cursor is followed ordered by rank (ascending or descending)
      Then  the rows come in (rank, id) order with no gaps or duplicates
    """
    # Given
    await _seed(cursor_adapter)
    descending = order_by.startswith("-")
    rows = [(i % 3, i) for i in range(1, TOTAL_ROWS + 1)]
    expected = [pk for _rank, pk in sorted(rows, reverse=descending)]

    # When
    pages = await _walk(cursor_adapter, order_by=order_by)

    # Then
    assert [pk for page in pages for pk in page] == expected


# ---------------------------------------------------------------------------
# Scenario: prev cursor returns the previous page
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
async def test_prev_cursor_returns_the_previous_page(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: a prev cursor goes back one page
      Given 25 rows and the second cursor page ordered by id
      When  list_paginated(cursor=prev_cursor) is called
      Then  rows 1-10 are returned in ascending order
      And   has_prev is false and has_next is true
    """
    # Given
    await _seed(cursor_adapter)
    first = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )
    second = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=first.next_cursor, page_size=PAGE_SIZE, order_by="id"
    )

    # When
    back = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=second.prev_cursor, page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert _ids(back.items) == list(range(1, 11))
    assert back.has_prev is False
    assert back.has_next is True


# ---------------------------------------------------------------------------
# Edge cases: empty table, first page, last page
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
async def test_cursor_mode_on_empty_table_returns_no_cursors(
    cursor_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: an empty table returns an empty cursor page
      Given no rows and pagination_mode="cursor"
      When  list_paginated(cursor=None, page_size=10) is called
      Then  items is empty, has_next and has_prev are false and both cursors are None
    """
    # When
    result = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert result.items == []
    assert result.has_next is False
    assert result.has_prev is False
    assert result.next_cursor is None
    assert result.prev_cursor is None
    assert result.total is None


@pending
@pytest.mark.anyio
async def test_first_page_has_no_prev_cursor(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: the first cursor page has nothing before it
      Given 25 rows and pagination_mode="cursor"
      When  the first page is fetched
      Then  has_prev is false and prev_cursor is None
    """
    # Given
    await _seed(cursor_adapter)

    # When
    result = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert result.has_prev is False
    assert result.prev_cursor is None


@pending
@pytest.mark.anyio
async def test_last_page_has_no_next_cursor(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: the last cursor page has nothing after it
      Given 25 rows and the next_cursor of the second page ordered by id
      When  the third page is fetched
      Then  rows 21-25 are returned with has_next false and next_cursor None
      And   has_prev is true
    """
    # Given
    await _seed(cursor_adapter)
    first = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )
    second = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=first.next_cursor, page_size=PAGE_SIZE, order_by="id"
    )

    # When
    last = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        cursor=second.next_cursor, page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert _ids(last.items) == list(range(21, 26))
    assert last.has_next is False
    assert last.next_cursor is None
    assert last.has_prev is True


@pending
@pytest.mark.anyio
async def test_exactly_one_full_page_has_no_next(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: a table holding exactly one page has no next page
      Given exactly 10 rows and pagination_mode="cursor"
      When  list_paginated(page_size=10) is called
      Then  all 10 rows are returned with has_next false and next_cursor None
    """
    # Given
    await _seed(cursor_adapter, count=PAGE_SIZE)

    # When
    result = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
        page_size=PAGE_SIZE, order_by="id"
    )

    # Then
    assert _ids(result.items) == list(range(1, PAGE_SIZE + 1))
    assert result.has_next is False
    assert result.next_cursor is None


# ---------------------------------------------------------------------------
# Scenario: cursor pages respect get_queryset() scoping
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
async def test_cursor_pages_keep_queryset_filters(cursor_adapter: SQLModelAdapter) -> None:
    """
    Scenario: a cursor does not bypass get_queryset() filters
      Given 25 rows and a queryset filter rank == 0
      When  next_cursor is followed ordered by id
      Then  only rows with rank 0 are returned
    """
    # Given
    await _seed(cursor_adapter)
    cursor_adapter.set_queryset_filter(lambda _request: {"rank": 0})

    # When
    pages = await _walk(cursor_adapter, order_by="id")

    # Then
    assert [pk for page in pages for pk in page] == [i for i in range(1, 26) if i % 3 == 0]


# ---------------------------------------------------------------------------
# Scenario: invalid/tampered cursor is rejected
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
@pytest.mark.parametrize(
    "cursor",
    [
        pytest.param("not-base64!", id="not-base64"),
        pytest.param(_forge_cursor({"k": [1, 1], "d": "next", "v": 2}), id="future-version"),
        pytest.param(_forge_cursor({"k": [1, 1], "d": "sideways", "v": 1}), id="bad-direction"),
        pytest.param(base64.urlsafe_b64encode(b"not json").decode().rstrip("="), id="not-json"),
    ],
)
async def test_invalid_cursor_raises_invalid_cursor_error(
    cursor_adapter: SQLModelAdapter, cursor: str
) -> None:
    """
    Scenario: invalid/tampered cursor is rejected
      Given 25 rows and pagination_mode="cursor"
      When  list_paginated(cursor=<malformed cursor>) is called
      Then  InvalidCursorError is raised
    """
    # Given
    await _seed(cursor_adapter)

    # When / Then
    with pytest.raises(core_adapters.InvalidCursorError):  # type: ignore[attr-defined]
        await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
            cursor=cursor, page_size=PAGE_SIZE, order_by="id"
        )


# ---------------------------------------------------------------------------
# Scenario: cursor mode falls back to offset when the sort is non-deterministic
# ---------------------------------------------------------------------------


@pending
@pytest.mark.anyio
async def test_nullable_sort_with_nulls_falls_back_to_offset(
    cursor_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: a sort column holding NULLs falls back to OFFSET
      Given 25 rows, one of them with score NULL, and pagination_mode="cursor"
      When  list_paginated(order_by="score", page_size=10) is called
      Then  a KeysetFallbackWarning is emitted
      And   the result is an offset page: 10 rows and total 25
    """
    # Given
    await _seed(cursor_adapter)
    await cursor_adapter.update(1, {"score": None})

    # When
    with pytest.warns(core_adapters.KeysetFallbackWarning):  # type: ignore[attr-defined]
        result = await cursor_adapter.list_paginated(  # type: ignore[attr-defined]
            page_size=PAGE_SIZE, order_by="score"
        )

    # Then
    assert len(result.items) == PAGE_SIZE
    assert result.total == TOTAL_ROWS
