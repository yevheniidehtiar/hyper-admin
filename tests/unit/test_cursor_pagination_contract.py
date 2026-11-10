"""Core cursor-pagination contract (story #227, SDD adapter-query-performance §A4).

Covers what ``core/`` owns: the cursor codec, ``ListResult`` and the default
``BaseAdapter.list_paginated()`` that adapters without keyset support inherit.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from hyperadmin.core.adapters import (
    BaseAdapter,
    Cursor,
    InvalidCursorError,
    KeysetFallbackWarning,
    ListResult,
    decode_cursor,
    encode_cursor,
)

ROWS = list(range(1, 26))


class OffsetOnlyAdapter(BaseAdapter):
    """A third-party adapter written before ``list_paginated`` existed."""

    def __init__(self) -> None:
        super().__init__(model=object, engine=object())
        self.calls: list[dict[str, Any]] = []

    async def list(  # type: ignore[override]
        self, page: int = 1, page_size: int = 10, **kwargs: Any
    ) -> tuple[list[int], int]:
        self.calls.append({"page": page, "page_size": page_size, **kwargs})
        start = (page - 1) * page_size
        return ROWS[start : start + page_size], len(ROWS)

    get = create = update = delete = get_related = get_schema = get_choices = (  # type: ignore[assignment]
        save_inline_rows
    ) = lambda *args, **kwargs: None


def _raw(payload: Any) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def test_cursor_round_trips_through_encode_and_decode() -> None:
    """
    Scenario: an encoded cursor decodes to its key and direction
      Given the key (42, "2026-01-01") and direction "next"
      When  the cursor is encoded and decoded again
      Then  the decoded cursor carries the same key and direction
      And   the encoded form is unpadded base64url
    """
    # When
    cursor = encode_cursor(42, "2026-01-01", "next")

    # Then
    assert decode_cursor(cursor) == Cursor(key=(42, "2026-01-01"), direction="next")
    assert "=" not in cursor
    assert json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))) == {
        "k": [42, "2026-01-01"],
        "d": "next",
        "v": 1,
    }


def test_non_json_key_values_are_encoded_as_strings() -> None:
    """
    Scenario: a UUID pk and a datetime sort value survive encoding
      Given a UUID pk and a datetime sort value
      When  a prev cursor is encoded and decoded
      Then  both values come back as their string form
    """
    # Given
    pk = uuid.uuid4()
    when = datetime(2026, 1, 1, tzinfo=UTC)

    # When
    decoded = decode_cursor(encode_cursor(pk, when, "prev"))

    # Then
    assert decoded == Cursor(key=(str(pk), str(when)), direction="prev")


@pytest.mark.parametrize(
    "cursor",
    [
        pytest.param("not-base64!", id="not-base64"),
        pytest.param(base64.urlsafe_b64encode(b"\xff\xfe").decode(), id="not-utf8"),
        pytest.param(_raw([1, 2]), id="not-an-object"),
        pytest.param(_raw({"k": [1, 1], "d": "next"}), id="no-version"),
        pytest.param(_raw({"k": [1, 1], "d": "next", "v": 2}), id="future-version"),
        pytest.param(_raw({"k": [1, 1], "d": "up", "v": 1}), id="bad-direction"),
        pytest.param(_raw({"k": 1, "d": "next", "v": 1}), id="key-not-a-list"),
        pytest.param(_raw({"k": [1], "d": "next", "v": 1}), id="key-too-short"),
    ],
)
def test_malformed_cursor_raises_invalid_cursor_error(cursor: str) -> None:
    """
    Scenario: a malformed or tampered cursor is rejected
      Given a cursor that is not a version-1 {k, d, v} payload
      When  it is decoded
      Then  InvalidCursorError (a ValueError) is raised
    """
    # When / Then
    with pytest.raises(InvalidCursorError, match="Invalid pagination cursor"):
        decode_cursor(cursor)
    assert issubclass(InvalidCursorError, ValueError)


def test_list_result_defaults_to_no_cursors() -> None:
    """
    Scenario: a ListResult built from items and a total has no neighbours
      Given items and a total only
      When  the ListResult is built
      Then  both cursors are None and has_next / has_prev are false
    """
    # When
    result = ListResult(items=[1], total=1)

    # Then
    assert (result.next_cursor, result.prev_cursor) == (None, None)
    assert (result.has_next, result.has_prev) == (False, False)


@pytest.mark.anyio
async def test_default_list_paginated_wraps_the_offset_page() -> None:
    """
    Scenario: an adapter without keyset support serves list_paginated from list()
      Given an offset-only adapter over 25 rows in the default pagination mode
      When  list_paginated(page=2, page_size=10, search="x") is called
      Then  rows 11-20 come back with total 25, no cursors, and both neighbours present
      And   list() receives the arguments without load_relations
    """
    # Given
    adapter = OffsetOnlyAdapter()
    assert adapter.pagination_mode == "offset"

    # When
    result = await adapter.list_paginated(page=2, page_size=10, search="x")

    # Then
    assert result == ListResult(items=list(range(11, 21)), total=25, has_next=True, has_prev=True)
    assert adapter.calls == [
        {
            "page": 2,
            "page_size": 10,
            "search": "x",
            "filters": None,
            "order_by": None,
            "search_fields": None,
        }
    ]


@pytest.mark.anyio
async def test_default_list_paginated_last_page_has_no_next() -> None:
    """
    Scenario: the last offset page has no following page
      Given an offset-only adapter over 25 rows
      When  list_paginated(page=3, page_size=10, load_relations=["owner"]) is called
      Then  rows 21-25 come back with has_next false and has_prev true
      And   list() receives load_relations
    """
    # Given
    adapter = OffsetOnlyAdapter()

    # When
    result = await adapter.list_paginated(page=3, page_size=10, load_relations=["owner"])

    # Then
    assert result.items == list(range(21, 26))
    assert (result.has_next, result.has_prev) == (False, True)
    assert adapter.calls[0]["load_relations"] == ["owner"]


@pytest.mark.anyio
async def test_default_list_paginated_in_cursor_mode_falls_back_with_a_warning() -> None:
    """
    Scenario: cursor mode on an adapter without keyset support falls back to OFFSET
      Given an offset-only adapter with pagination_mode="cursor" and a valid cursor
      When  list_paginated(cursor=...) is called
      Then  a KeysetFallbackWarning is emitted
      And   the first offset page is returned with its total
    """
    # Given
    adapter = OffsetOnlyAdapter()
    adapter.pagination_mode = "cursor"

    # When
    with pytest.warns(KeysetFallbackWarning, match="OffsetOnlyAdapter"):
        result = await adapter.list_paginated(cursor=encode_cursor(10, 10, "next"))

    # Then
    assert result.items == list(range(1, 11))
    assert result.total == 25


@pytest.mark.anyio
async def test_default_list_paginated_rejects_a_tampered_cursor() -> None:
    """
    Scenario: a tampered cursor is rejected even without keyset support
      Given an offset-only adapter
      When  list_paginated(cursor="garbage!") is called
      Then  InvalidCursorError is raised before list() runs
    """
    # Given
    adapter = OffsetOnlyAdapter()

    # When / Then
    with pytest.raises(InvalidCursorError):
        await adapter.list_paginated(cursor="garbage!")
    assert adapter.calls == []
