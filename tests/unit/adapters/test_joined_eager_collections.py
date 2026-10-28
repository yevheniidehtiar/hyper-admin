"""Adapters on models with ``lazy="joined"`` collection relationships (#718).

SQLAlchemy 2.x refuses to fetch ORM results that joined-eager-load a collection unless
``Result.unique()`` is called first. Each scenario runs against a plain SQLAlchemy model
(``SQLAlchemyAdapter``) and a SQLModel model (both adapters).
"""

from typing import Any

import pytest
from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter


class Base(DeclarativeBase):
    pass


class SAParent(Base):
    __tablename__ = "joined_sa_parent"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    children: Mapped[list["SAChild"]] = relationship(back_populates="parent", lazy="joined")


class SAChild(Base):
    __tablename__ = "joined_sa_child"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    parent_id: Mapped[int] = mapped_column(ForeignKey("joined_sa_parent.id"))
    parent: Mapped["SAParent"] = relationship(back_populates="children")


class SMParent(SQLModel, table=True):
    __tablename__ = "joined_sm_parent"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    children: list["SMChild"] = Relationship(
        back_populates="parent", sa_relationship_kwargs={"lazy": "joined"}
    )


class SMChild(SQLModel, table=True):
    __tablename__ = "joined_sm_child"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    parent_id: int | None = Field(default=None, foreign_key="joined_sm_parent.id")
    parent: "SMParent" = Relationship(back_populates="children")


CASES = [
    pytest.param(SQLAlchemyAdapter, SAParent, SAChild, id="sqlalchemy-plain"),
    pytest.param(SQLAlchemyAdapter, SMParent, SMChild, id="sqlalchemy-sqlmodel"),
    pytest.param(SQLModelAdapter, SMParent, SMChild, id="sqlmodel"),
]


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    return eng


async def _seed(engine: AsyncEngine, parent: type, child: type) -> list[Any]:
    """Three parents with two children each, inserted through a plain session."""
    parents = [parent(name=f"p{i}") for i in range(3)]
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add_all(parents)
        await session.flush()
        session.add_all(
            child(name=f"c{i}{j}", parent_id=p.id) for i, p in enumerate(parents) for j in range(2)
        )
        await session.commit()
    return parents


@pytest.mark.anyio
@pytest.mark.parametrize(("adapter_cls", "parent", "child"), CASES)
async def test_list_returns_each_parent_once(
    engine: AsyncEngine, adapter_cls: type, parent: type, child: type
) -> None:
    """Scenario: list de-duplicates rows multiplied by a joined collection.

    Given 3 parents with 2 children each and a lazy="joined" children relationship
    When the parent list is fetched
    Then it returns 3 rows and a total count of 3
    """
    # Given
    await _seed(engine, parent, child)
    adapter = adapter_cls(model=parent, engine=engine)

    # When
    items, total = await adapter.list(page=1, page_size=10)

    # Then
    assert total == 3
    assert sorted(p.name for p in items) == ["p0", "p1", "p2"]
    assert all(len(p.children) == 2 for p in items)


@pytest.mark.anyio
@pytest.mark.parametrize(("adapter_cls", "parent", "child"), CASES)
async def test_list_paginates_parents_not_joined_rows(
    engine: AsyncEngine, adapter_cls: type, parent: type, child: type
) -> None:
    """Scenario: pagination counts parents, not joined rows.

    Given 3 parents with 2 children each
    When the list is fetched with page_size=2
    Then page 1 has 2 parents and page 2 has 1 parent
    """
    # Given
    await _seed(engine, parent, child)
    adapter = adapter_cls(model=parent, engine=engine)

    # When
    page_1, _ = await adapter.list(page=1, page_size=2, order_by="id")
    page_2, _ = await adapter.list(page=2, page_size=2, order_by="id")

    # Then
    assert [p.name for p in page_1] == ["p0", "p1"]
    assert [p.name for p in page_2] == ["p2"]


@pytest.mark.anyio
@pytest.mark.parametrize(("adapter_cls", "parent", "child"), CASES)
async def test_get_with_queryset_filter_returns_parent(
    engine: AsyncEngine, adapter_cls: type, parent: type, child: type
) -> None:
    """Scenario: a row-scoped get() on a joined-collection model.

    Given a get_queryset filter and a lazy="joined" children relationship
    When get() fetches a visible parent
    Then the parent is returned with its children
    """
    # Given
    parents = await _seed(engine, parent, child)
    adapter = adapter_cls(model=parent, engine=engine)
    adapter.set_queryset_filter(lambda _request: {"name": "p1"})

    # When
    found = await adapter.get(pk=parents[1].id)

    # Then
    assert found is not None
    assert found.name == "p1"
    assert len(found.children) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(("adapter_cls", "parent", "child"), CASES)
async def test_get_related_returns_children(
    engine: AsyncEngine, adapter_cls: type, parent: type, child: type
) -> None:
    """Scenario: get_related() on a joined collection.

    Given a parent with 2 children through a lazy="joined" relationship
    When get_related() is called for "children"
    Then both children are returned
    """
    # Given
    parents = await _seed(engine, parent, child)
    adapter = adapter_cls(model=parent, engine=engine)

    # When
    related = await adapter.get_related(parents[0].id, "children")

    # Then
    assert sorted(c.name for c in related) == ["c00", "c01"]


@pytest.mark.anyio
@pytest.mark.parametrize(("adapter_cls", "parent", "child"), CASES)
async def test_get_choices_on_target_with_joined_collection(
    engine: AsyncEngine, adapter_cls: type, parent: type, child: type
) -> None:
    """Scenario: relation choices whose target model joined-loads a collection.

    Given a child model whose "parent" target has a lazy="joined" collection
    When get_choices() is called for "parent"
    Then each parent is offered once
    """
    # Given
    await _seed(engine, parent, child)
    adapter = adapter_cls(model=child, engine=engine)

    # When
    choices = await adapter.get_choices("parent")

    # Then
    assert sorted(c["label"] for c in choices) == ["p0", "p1", "p2"]
