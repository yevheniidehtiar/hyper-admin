"""Keyset pagination edge cases in ``SQLModelAdapter.list_paginated`` (story #228, SDD §A4).

The contract tests live in ``test_adapter_keyset_pagination.py``; these cover the fallbacks,
cursor tampering, backwards paging on descending sorts and non-integer sort keys.
"""

import enum
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import (
    InvalidCursorError,
    KeysetFallbackWarning,
    ListResult,
    encode_cursor,
)

PAGE_SIZE = 4
ROWS = 10


class Shade(enum.Enum):
    """A plain (non-str) enum: its members are not JSON-serialisable on their own."""

    DARK = 1
    LIGHT = 2


class KsOwner(SQLModel, table=True):
    __tablename__ = "test_ks_owner"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    pets: list["KsPet"] = Relationship(back_populates="owner")


class KsPet(SQLModel, table=True):
    __tablename__ = "test_ks_pet"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    born: datetime
    shade: Shade
    weight: int | None = None
    owner_id: int | None = Field(default=None, foreign_key="test_ks_owner.id")
    owner: KsOwner | None = Relationship(back_populates="pets")


class KsPair(SQLModel, table=True):
    __tablename__ = "test_ks_pair"

    left: int = Field(primary_key=True)
    right: int = Field(primary_key=True)


BASE = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return eng


@pytest.fixture
async def pets(engine: AsyncEngine) -> SQLModelAdapter:
    """Ten pets: ``born`` ascending with id, ``shade`` alternating, all owned by one owner."""
    owners = SQLModelAdapter(model=KsOwner, engine=engine)
    owner = await owners.create({"name": "alice"})
    adapter = SQLModelAdapter(model=KsPet, engine=engine)
    for i in range(1, ROWS + 1):
        await adapter.create(
            {
                "name": f"pet-{i:02d}",
                "born": BASE + timedelta(days=i),
                "shade": Shade.DARK if i % 2 else Shade.LIGHT,
                "weight": i,
                "owner_id": owner.id,
            }
        )
    adapter.pagination_mode = "cursor"
    return adapter


def _ids(result: ListResult) -> list[int]:
    return [row.id for row in result.items]


async def _walk(adapter: SQLModelAdapter, **kwargs: Any) -> list[ListResult]:
    pages = [await adapter.list_paginated(page_size=PAGE_SIZE, **kwargs)]
    while pages[-1].has_next:
        pages.append(
            await adapter.list_paginated(
                cursor=pages[-1].next_cursor, page_size=PAGE_SIZE, **kwargs
            )
        )
    return pages


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("order_by", "expected"),
    [
        pytest.param("-id", [10, 9, 8, 7], id="pk-desc"),
        pytest.param("-born", [10, 9, 8, 7], id="column-desc"),
        pytest.param("born", [1, 2, 3, 4], id="column-asc"),
    ],
)
async def test_prev_cursor_returns_previous_page_in_sort_order(
    pets: SQLModelAdapter, order_by: str, expected: list[int]
) -> None:
    """
    Scenario: a prev cursor goes back one page in any sort direction
      Given ten pets and the second cursor page for the sort
      When  its prev_cursor is followed
      Then  the first page comes back in sort order with has_prev false and has_next true
    """
    # Given
    first = await pets.list_paginated(page_size=PAGE_SIZE, order_by=order_by)
    second = await pets.list_paginated(
        cursor=first.next_cursor, page_size=PAGE_SIZE, order_by=order_by
    )

    # When
    back = await pets.list_paginated(
        cursor=second.prev_cursor, page_size=PAGE_SIZE, order_by=order_by
    )

    # Then
    assert _ids(back) == expected
    assert back.has_prev is False
    assert back.has_next is True
    assert back.next_cursor is not None
    assert back.prev_cursor is None


@pytest.mark.anyio
async def test_prev_cursor_from_middle_page_keeps_both_links(pets: SQLModelAdapter) -> None:
    """
    Scenario: going back to a middle page keeps both directions open
      Given ten pets and the last of three cursor pages ordered by born
      When  its prev_cursor is followed
      Then  the middle page (5-8) is returned with has_prev and has_next both true
    """
    # Given
    pages = await _walk(pets, order_by="born")

    # When
    back = await pets.list_paginated(
        cursor=pages[-1].prev_cursor, page_size=PAGE_SIZE, order_by="born"
    )

    # Then
    assert _ids(back) == [5, 6, 7, 8]
    assert back.has_prev is True
    assert back.has_next is True


@pytest.mark.anyio
@pytest.mark.parametrize("order_by", ["born", "-born", "shade", "-shade", "name"])
async def test_cursor_chain_on_typed_sort_column_visits_every_row_once(
    pets: SQLModelAdapter, order_by: str
) -> None:
    """
    Scenario: datetime, enum and string sort keys survive the cursor round trip
      Given ten pets and pagination_mode="cursor"
      When  next_cursor is followed for the sort
      Then  every pet is visited exactly once in (sort, id) order
    """
    # Given
    descending = order_by.startswith("-")
    attr = order_by.lstrip("-")
    rows, _total = await pets.list(page_size=ROWS)

    def key(row: KsPet) -> tuple[Any, int]:
        # SQLAlchemy's Enum type stores (and so sorts by) the member name.
        value = getattr(row, attr)
        return (value.name if isinstance(value, Shade) else value, row.id or 0)

    expected = [row.id for row in sorted(rows, key=key, reverse=descending)]

    # When
    pages = await _walk(pets, order_by=order_by)

    # Then
    assert [pk for page in pages for pk in _ids(page)] == expected
    assert all(page.total is None for page in pages)


@pytest.mark.anyio
async def test_nullable_sort_column_without_nulls_pages_by_keyset(
    pets: SQLModelAdapter,
) -> None:
    """
    Scenario: a nullable sort column with no NULLs still pages by keyset
      Given ten pets whose nullable weight is always set
      When  list_paginated(order_by="weight") is called
      Then  a cursor page is returned with total None and a next cursor
    """
    # When
    result = await pets.list_paginated(page_size=PAGE_SIZE, order_by="weight")

    # Then
    assert _ids(result) == [1, 2, 3, 4]
    assert result.total is None
    assert result.next_cursor is not None


@pytest.mark.anyio
async def test_nulls_outside_the_filtered_rows_do_not_force_offset(
    pets: SQLModelAdapter,
) -> None:
    """
    Scenario: only NULLs inside the filtered rows force the OFFSET fallback
      Given ten pets, pet 10 with weight NULL, and a filter excluding pet 10
      When  list_paginated(order_by="weight", filters={"shade": DARK}) is called
      Then  the page is a keyset page of the dark pets
    """
    # Given
    await pets.update(10, {"weight": None})

    # When
    result = await pets.list_paginated(
        page_size=PAGE_SIZE, order_by="weight", filters={"shade": Shade.DARK}
    )

    # Then
    assert _ids(result) == [1, 3, 5, 7]
    assert result.total is None


@pytest.mark.anyio
async def test_fallback_page_honours_page_number(pets: SQLModelAdapter) -> None:
    """
    Scenario: the OFFSET fallback serves the requested page number
      Given ten pets with one NULL weight
      When  list_paginated(page=3, order_by="weight") is called
      Then  a KeysetFallbackWarning is emitted
      And   the last two rows are returned with total 10, has_prev true and has_next false
    """
    # Given
    await pets.update(1, {"weight": None})

    # When
    with pytest.warns(KeysetFallbackWarning, match="holds NULLs"):
        result = await pets.list_paginated(page=3, page_size=PAGE_SIZE, order_by="weight")

    # Then
    assert len(result.items) == 2
    assert result.total == ROWS
    assert result.has_prev is True
    assert result.has_next is False


@pytest.mark.anyio
async def test_composite_primary_key_falls_back_to_offset(engine: AsyncEngine) -> None:
    """
    Scenario: a composite primary key falls back to OFFSET
      Given a model keyed by (left, right) and pagination_mode="cursor"
      When  list_paginated() is called
      Then  a KeysetFallbackWarning names the composite key
      And   the result is an offset page with a total
    """
    # Given
    adapter = SQLModelAdapter(model=KsPair, engine=engine)
    for i in range(3):
        await adapter.create({"left": i, "right": i})
    adapter.pagination_mode = "cursor"

    # When
    with pytest.warns(KeysetFallbackWarning, match="composite primary key"):
        result = await adapter.list_paginated(page_size=PAGE_SIZE)

    # Then
    assert len(result.items) == 3
    assert result.total == 3


@pytest.mark.anyio
async def test_unknown_sort_field_warns_then_fails_like_offset_mode(
    pets: SQLModelAdapter,
) -> None:
    """
    Scenario: an unmapped sort target is not paged by keyset
      Given ten pets and pagination_mode="cursor"
      When  list_paginated(order_by="nope") is called
      Then  a KeysetFallbackWarning is emitted
      And   the offset path rejects the unknown field as it does in offset mode
    """
    # When / Then
    with (
        pytest.warns(KeysetFallbackWarning, match="not a mapped column"),
        pytest.raises(AttributeError),
    ):
        await pets.list_paginated(page_size=PAGE_SIZE, order_by="nope")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("cursor", "order_by"),
    [
        pytest.param(encode_cursor("abc", "abc", "next"), "id", id="pk-not-int"),
        pytest.param(encode_cursor(1, "yesterday", "next"), "born", id="sort-not-datetime"),
        pytest.param(encode_cursor([1], 1, "next"), "id", id="pk-not-scalar"),
        pytest.param(encode_cursor(1, {"x": 1}, "next"), "born", id="sort-not-scalar"),
    ],
)
async def test_cursor_key_of_wrong_type_is_rejected(
    pets: SQLModelAdapter, cursor: str, order_by: str
) -> None:
    """
    Scenario: a well-formed cursor whose key does not fit the columns is rejected
      Given ten pets and a cursor whose pk or sort value has the wrong type
      When  list_paginated(cursor=...) is called
      Then  InvalidCursorError is raised
    """
    # When / Then
    with pytest.raises(InvalidCursorError):
        await pets.list_paginated(cursor=cursor, page_size=PAGE_SIZE, order_by=order_by)


@pytest.mark.anyio
async def test_cursor_past_the_last_row_returns_empty_page(pets: SQLModelAdapter) -> None:
    """
    Scenario: a cursor past every remaining row returns an empty page
      Given ten pets and the next cursor of the first page
      And   every later pet has been deleted
      When  that cursor is followed
      Then  items is empty with no cursors and no further pages
    """
    # Given
    first = await pets.list_paginated(page_size=PAGE_SIZE, order_by="id")
    for pk in range(PAGE_SIZE + 1, ROWS + 1):
        await pets.delete(pk)

    # When
    result = await pets.list_paginated(cursor=first.next_cursor, page_size=PAGE_SIZE, order_by="id")

    # Then
    assert result.items == []
    assert result.has_next is result.has_prev is False
    assert result.next_cursor is result.prev_cursor is None


@pytest.mark.anyio
async def test_cursor_pages_apply_search_and_load_relations(pets: SQLModelAdapter) -> None:
    """
    Scenario: search and eager-loaded relations apply to every cursor page
      Given ten pets of one owner
      When  next_cursor is followed with search="pet-0" and load_relations=["owner"]
      Then  only pets 1-9 are visited and each row carries its loaded owner
    """
    # When
    pages = await _walk(pets, order_by="id", search="pet-0", load_relations=["owner"])

    # Then
    rows = [row for page in pages for row in page.items]
    assert [row.id for row in rows] == list(range(1, 10))
    assert {row.owner.name for row in rows} == {"alice"}


@pytest.mark.anyio
async def test_fallback_page_applies_load_relations(pets: SQLModelAdapter) -> None:
    """
    Scenario: the OFFSET fallback still eager-loads the requested relations
      Given ten pets with one NULL weight
      When  list_paginated(order_by="weight", load_relations=["owner"]) is called
      Then  every row carries its loaded owner
    """
    # Given
    await pets.update(1, {"weight": None})

    # When
    with pytest.warns(KeysetFallbackWarning):
        result = await pets.list_paginated(
            page_size=PAGE_SIZE, order_by="weight", load_relations=["owner"]
        )

    # Then
    assert {row.owner.name for row in result.items} == {"alice"}


@pytest.mark.anyio
async def test_offset_mode_list_paginated_ignores_keyset(pets: SQLModelAdapter) -> None:
    """
    Scenario: offset mode keeps page numbers on the SQLModel adapter
      Given ten pets and pagination_mode="offset"
      When  list_paginated(page=2) is called
      Then  pets 5-8 are returned with total 10 and both neighbours flagged
    """
    # Given
    pets.pagination_mode = "offset"

    # When
    result = await pets.list_paginated(page=2, page_size=PAGE_SIZE, order_by="id")

    # Then
    assert _ids(result) == [5, 6, 7, 8]
    assert result.total == ROWS
    assert result.has_prev is result.has_next is True
