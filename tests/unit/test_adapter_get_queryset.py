"""Unit tests for the BaseAdapter.get_queryset hook (BDD scenarios from issue #478).

Each test maps 1:1 to a scenario in
``.meta/epics/.../featadapters-add-getqueryset-hook-to-baseadapter-sqlmodelada.md``.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter


class Document(SQLModel, table=True):
    """Test model with an ``owner_id`` column for row-level filter scenarios."""

    __tablename__ = "test_get_queryset_document"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    owner_id: int = Field(default=0, index=True)


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return eng


@pytest.fixture
async def sqlmodel_adapter(engine: AsyncEngine) -> SQLModelAdapter:
    return SQLModelAdapter(model=Document, engine=engine)


@pytest.fixture
async def sqlalchemy_adapter(engine: AsyncEngine) -> SQLAlchemyAdapter:
    return SQLAlchemyAdapter(model=Document, engine=engine)


async def _seed(adapter: SQLModelAdapter | SQLAlchemyAdapter, owner_counts: dict[int, int]) -> None:
    """Create N rows per owner_id."""
    for owner_id, count in owner_counts.items():
        for i in range(count):
            await adapter.create({"title": f"doc-{owner_id}-{i}", "owner_id": owner_id})


# ---------------------------------------------------------------------------
# Scenario: get_queryset filters list results
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_queryset_filters_list_results_sqlmodel(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: get_queryset filters are applied to list results
      Given adapter has get_queryset() returning {"owner_id": 1}
      When  adapter.list() is called
      Then  only matching records are returned
    """
    # Given
    await _seed(sqlmodel_adapter, {1: 3, 2: 5})
    sqlmodel_adapter.set_queryset_filter(lambda _request: {"owner_id": 1})

    # When
    rows, total = await sqlmodel_adapter.list(page=1, page_size=50)

    # Then
    assert total == 3
    assert all(row.owner_id == 1 for row in rows)


@pytest.mark.anyio
async def test_get_queryset_filters_list_results_sqlalchemy(
    sqlalchemy_adapter: SQLAlchemyAdapter,
) -> None:
    # Given
    await _seed(sqlalchemy_adapter, {1: 3, 2: 5})
    sqlalchemy_adapter.set_queryset_filter(lambda _request: {"owner_id": 1})

    # When
    rows, total = await sqlalchemy_adapter.list(page=1, page_size=50)

    # Then
    assert total == 3
    assert all(row.owner_id == 1 for row in rows)


# ---------------------------------------------------------------------------
# Scenario: get_queryset filters get() results (returns None when row excluded)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_queryset_filters_get_results_sqlmodel(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: get_queryset filters are applied to get() results
      Given adapter has get_queryset() returning {"owner_id": 1}
      When  adapter.get(pk=X) is called for a record with owner_id=2
      Then  result is None (record filtered out)
    """
    # Given
    visible = await sqlmodel_adapter.create({"title": "mine", "owner_id": 1})
    hidden = await sqlmodel_adapter.create({"title": "yours", "owner_id": 2})
    sqlmodel_adapter.set_queryset_filter(lambda _request: {"owner_id": 1})

    # When
    visible_result = await sqlmodel_adapter.get(pk=visible.id)
    hidden_result = await sqlmodel_adapter.get(pk=hidden.id)

    # Then
    assert visible_result is not None
    assert visible_result.id == visible.id
    assert hidden_result is None


@pytest.mark.anyio
async def test_get_queryset_filters_get_results_sqlalchemy(
    sqlalchemy_adapter: SQLAlchemyAdapter,
) -> None:
    # Given
    visible = await sqlalchemy_adapter.create({"title": "mine", "owner_id": 1})
    hidden = await sqlalchemy_adapter.create({"title": "yours", "owner_id": 2})
    sqlalchemy_adapter.set_queryset_filter(lambda _request: {"owner_id": 1})

    # When
    visible_result = await sqlalchemy_adapter.get(pk=visible.id)
    hidden_result = await sqlalchemy_adapter.get(pk=hidden.id)

    # Then
    assert visible_result is not None
    assert visible_result.id == visible.id
    assert hidden_result is None


# ---------------------------------------------------------------------------
# Scenario: empty get_queryset is a no-op (backward compatible)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_get_queryset_is_no_op_sqlmodel(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: empty get_queryset returns all records (backward compatible)
      Given adapter has default get_queryset() returning {}
      When  adapter.list() is called
      Then  all records are returned (no extra filtering)
    """
    # Given
    await _seed(sqlmodel_adapter, {1: 3, 2: 5})

    # When (no set_queryset_filter call — default behavior)
    rows, total = await sqlmodel_adapter.list(page=1, page_size=50)

    # Then
    assert total == 8
    assert len(rows) == 8


@pytest.mark.anyio
async def test_empty_get_queryset_is_no_op_sqlalchemy(
    sqlalchemy_adapter: SQLAlchemyAdapter,
) -> None:
    # Given
    await _seed(sqlalchemy_adapter, {1: 3, 2: 5})

    # When
    rows, total = await sqlalchemy_adapter.list(page=1, page_size=50)

    # Then
    assert total == 8
    assert len(rows) == 8


@pytest.mark.anyio
async def test_default_get_queryset_returns_empty_dict(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """Default ``get_queryset`` returns an empty dict, never ``None``."""
    assert sqlmodel_adapter.get_queryset() == {}
    assert sqlmodel_adapter.get_queryset(request=None) == {}


# ---------------------------------------------------------------------------
# Scenario: get_queryset count reflects filtered total
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_queryset_count_reflects_filter_sqlmodel(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """
    Scenario: get_queryset count reflects filtered results
      Given 100 records total, 30 matching {"owner_id": 1}
      When  adapter.list() is called with queryset filter {"owner_id": 1}
      Then  total count is 30
    """
    # Given
    await _seed(sqlmodel_adapter, {1: 30, 2: 70})
    sqlmodel_adapter.set_queryset_filter(lambda _request: {"owner_id": 1})

    # When
    rows, total = await sqlmodel_adapter.list(page=1, page_size=10)

    # Then
    assert total == 30
    assert len(rows) == 10  # paginated
    assert all(row.owner_id == 1 for row in rows)


@pytest.mark.anyio
async def test_get_queryset_count_reflects_filter_sqlalchemy(
    sqlalchemy_adapter: SQLAlchemyAdapter,
) -> None:
    # Given
    await _seed(sqlalchemy_adapter, {1: 30, 2: 70})
    sqlalchemy_adapter.set_queryset_filter(lambda _request: {"owner_id": 1})

    # When
    rows, total = await sqlalchemy_adapter.list(page=1, page_size=10)

    # Then
    assert total == 30
    assert len(rows) == 10
    assert all(row.owner_id == 1 for row in rows)


# ---------------------------------------------------------------------------
# Edge cases (per SDD §"Edge Cases & Error Handling")
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_queryset_non_dict_raises_type_error(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """If a custom ``get_queryset`` returns a non-dict, raise ``TypeError`` early."""
    sqlmodel_adapter.set_queryset_filter(lambda _request: ["not", "a", "dict"])  # type: ignore[arg-type,return-value]
    with pytest.raises(TypeError):
        await sqlmodel_adapter.list(page=1, page_size=10)


@pytest.mark.anyio
async def test_get_queryset_non_dict_raises_type_error_on_get(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    created = await sqlmodel_adapter.create({"title": "x", "owner_id": 1})
    sqlmodel_adapter.set_queryset_filter(lambda _request: 42)  # type: ignore[arg-type,return-value]
    with pytest.raises(TypeError):
        await sqlmodel_adapter.get(pk=created.id)


@pytest.mark.anyio
async def test_set_queryset_filter_evaluated_per_request(
    sqlmodel_adapter: SQLModelAdapter,
) -> None:
    """The filter callable is re-evaluated on every list/get — no caching."""
    await _seed(sqlmodel_adapter, {1: 2, 2: 2})

    state: dict[str, Any] = {"current_owner": 1}

    def dynamic_filter(_request: Any) -> dict[str, Any]:
        return {"owner_id": state["current_owner"]}

    sqlmodel_adapter.set_queryset_filter(dynamic_filter)

    _, total_owner_1 = await sqlmodel_adapter.list(page=1, page_size=10)
    state["current_owner"] = 2
    _, total_owner_2 = await sqlmodel_adapter.list(page=1, page_size=10)

    assert total_owner_1 == 2
    assert total_owner_2 == 2
