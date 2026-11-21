"""``HyperAdminModel.before_save`` / ``after_save`` run on every adapter create and update.

v1.0 public API audit (st-v100-freeze-03), finding 2: the hooks existed but nothing
called them. The two delete hooks were removed instead.
"""

from typing import Any, ClassVar

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import run_save_hook
from hyperadmin.core.model import HyperAdminModel


class _CrudStubs:
    """The abstract CRUD methods of HyperAdminModel; the adapters do the real work."""

    @classmethod
    async def create(cls, data: dict[str, Any]) -> Any:
        raise NotImplementedError

    @classmethod
    async def get(cls, pk: Any) -> Any:
        raise NotImplementedError

    async def update(self, data: dict[str, Any]) -> None:
        raise NotImplementedError

    async def delete(self) -> None:
        raise NotImplementedError


class HookedNote(_CrudStubs, SQLModel, HyperAdminModel, table=True):
    __tablename__ = "test_hooked_note"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    slug: str = ""

    calls: ClassVar[list[tuple[str, Any, str]]] = []

    async def before_save(self) -> None:
        # Changes made here are saved with the row.
        self.slug = self.title.lower().replace(" ", "-")
        HookedNote.calls.append(("before_save", self.id, self.title))

    async def after_save(self) -> None:
        HookedNote.calls.append(("after_save", self.id, self.title))


class PlainNote(SQLModel, table=True):
    __tablename__ = "test_plain_note"
    id: int | None = Field(default=None, primary_key=True)
    title: str

    calls: ClassVar[list[str]] = []

    async def before_save(self) -> None:
        PlainNote.calls.append("before_save")


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    HookedNote.calls = []
    PlainNote.calls = []
    return eng


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_cls(request: pytest.FixtureRequest) -> Any:
    return request.param


async def _stored_slug(engine: AsyncEngine, pk: int) -> str:
    async with AsyncSession(engine) as session:
        row = await session.get(HookedNote, pk)
        assert row is not None
        return row.slug


@pytest.mark.anyio
async def test_create_runs_before_save_then_after_save(
    engine: AsyncEngine, adapter_cls: Any
) -> None:
    """
    Scenario: create calls both save hooks in order
      Given a HyperAdminModel table model with before_save and after_save
      When  the adapter creates a row
      Then  before_save runs before the commit (no id yet) and after_save after it
      And   a value set in before_save is stored
    """
    adapter = adapter_cls(HookedNote, engine)

    created = await adapter.create(data={"title": "Hello World"})

    assert HookedNote.calls == [
        ("before_save", None, "Hello World"),
        ("after_save", created.id, "Hello World"),
    ]
    assert await _stored_slug(engine, created.id) == "hello-world"


@pytest.mark.anyio
async def test_update_runs_both_save_hooks_with_the_new_values(
    engine: AsyncEngine, adapter_cls: Any
) -> None:
    """
    Scenario: update calls both save hooks on the changed row
      Given a stored HyperAdminModel row
      When  the adapter updates its title
      Then  before_save and after_save both see the new title
      And   the slug set in before_save is stored
    """
    adapter = adapter_cls(HookedNote, engine)
    created = await adapter.create(data={"title": "Draft"})
    HookedNote.calls = []

    await adapter.update(pk=created.id, data={"title": "Final Copy"})

    assert HookedNote.calls == [
        ("before_save", created.id, "Final Copy"),
        ("after_save", created.id, "Final Copy"),
    ]
    assert await _stored_slug(engine, created.id) == "final-copy"


@pytest.mark.anyio
async def test_update_of_a_missing_row_runs_no_hook(engine: AsyncEngine, adapter_cls: Any) -> None:
    """
    Scenario: updating a row that does not exist calls no hook
      Given no stored row with id 99
      When  the adapter updates id 99
      Then  no save hook runs and None is returned
    """
    adapter = adapter_cls(HookedNote, engine)

    assert await adapter.update(pk=99, data={"title": "Ghost"}) is None
    assert HookedNote.calls == []


@pytest.mark.anyio
async def test_a_failing_before_save_aborts_the_create(engine: AsyncEngine) -> None:
    """
    Scenario: an exception in before_save stops the save
      Given a HyperAdminModel whose before_save raises
      When  the adapter creates a row
      Then  the error propagates and no row is stored
    """

    async def _refuse(self: HookedNote) -> None:
        raise ValueError("title is reserved")

    adapter = SQLModelAdapter(HookedNote, engine)
    original = HookedNote.before_save
    HookedNote.before_save = _refuse  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError, match="reserved"):
            await adapter.create(data={"title": "admin"})
    finally:
        HookedNote.before_save = original  # type: ignore[method-assign]

    _items, total = await adapter.list()
    assert total == 0


@pytest.mark.anyio
async def test_a_model_that_is_not_a_hyperadmin_model_is_left_alone(
    engine: AsyncEngine, adapter_cls: Any
) -> None:
    """
    Scenario: a same-named method on another model is not called
      Given a plain SQLModel table model with its own before_save method
      When  the adapter creates a row
      Then  that method is not called
    """
    adapter = adapter_cls(PlainNote, engine)

    await adapter.create(data={"title": "Untouched"})

    assert PlainNote.calls == []


@pytest.mark.anyio
async def test_run_save_hook_ignores_plain_objects() -> None:
    """
    Scenario: run_save_hook on a non-model object is a no-op
      Given an object that is not a HyperAdminModel
      When  run_save_hook(obj, "after_save") is awaited
      Then  nothing happens and no error is raised
    """
    await run_save_hook(object(), "after_save")


def test_hyperadmin_model_has_no_delete_hooks() -> None:
    """
    Scenario: only the two save hooks remain
      Given the HyperAdminModel base class
      When  its hook methods are listed
      Then  before_save and after_save exist and before_delete / after_delete do not
    """
    assert callable(HyperAdminModel.before_save)
    assert callable(HyperAdminModel.after_save)
    assert not hasattr(HyperAdminModel, "before_delete")
    assert not hasattr(HyperAdminModel, "after_delete")
