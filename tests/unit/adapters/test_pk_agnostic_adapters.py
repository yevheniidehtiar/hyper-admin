"""pk-agnostic adapter behaviour (st-v058-byoa-22).

``SQLModelAdapter`` and ``SQLAlchemyAdapter`` use ``self.pk`` (introspected via
``adapters/introspection.py``, story st-v058-byoa-15) in ``get``, ``get_related``,
``update``, ``delete``, ``get_choices`` and ``save_inline_rows``, so a natural
UUID or int primary key works the same way the historical ``int id`` always has.
Every scenario below runs against both adapters.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import InlineRowNotOwnedError
from hyperadmin.core.inlines import InlineModelSpec

AdapterClass = type[SQLModelAdapter] | type[SQLAlchemyAdapter]

# ---------------------------------------------------------------------------
# Schema fixtures
# ---------------------------------------------------------------------------


class PkCountry(SQLModel, table=True):
    __tablename__ = "pk_agnostic_countries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str

    cities: Mapped[list["PkCity"]] = Relationship(back_populates="country")

    def __str__(self) -> str:
        return self.name


class PkCity(SQLModel, table=True):
    __tablename__ = "pk_agnostic_cities"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    country_id: uuid.UUID | None = Field(default=None, foreign_key="pk_agnostic_countries.id")

    country: Mapped[PkCountry | None] = Relationship(back_populates="cities")

    def __str__(self) -> str:
        return self.name


class PkWidget(SQLModel, table=True):
    __tablename__ = "pk_agnostic_widgets"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class PkPart(SQLModel, table=True):
    __tablename__ = "pk_agnostic_parts"

    id: int | None = Field(default=None, primary_key=True)
    sku: str
    widget_id: int | None = Field(default=None, foreign_key="pk_agnostic_widgets.id")


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_class(request: pytest.FixtureRequest) -> AdapterClass:
    return request.param


@pytest.fixture
async def country(engine: AsyncEngine) -> Any:
    adapter = SQLModelAdapter(PkCountry, engine)
    return await adapter.create({"name": "United Kingdom"})


@pytest.fixture
async def city(engine: AsyncEngine, country: Any) -> Any:
    adapter = SQLModelAdapter(PkCity, engine)
    return await adapter.create({"name": "London", "country_id": country.id})


# ---------------------------------------------------------------------------
# Scenario: get by UUID string
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_by_uuid_string(
    engine: AsyncEngine, city: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: get by UUID string
      Given a UUID-keyed row
      When  adapter.get(str(uuid)) runs
      Then  the row is returned
    """
    adapter = adapter_class(PkCity, engine)

    result = await adapter.get(str(city.id))

    assert result is not None
    assert result.id == city.id


# ---------------------------------------------------------------------------
# Scenario: garbage key returns None
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_garbage_key_returns_none(engine: AsyncEngine, adapter_class: AdapterClass) -> None:
    """
    Scenario: garbage key returns None
      Given a UUID-keyed model on SQLite
      When  adapter.get('garbage') runs
      Then  None is returned
    """
    adapter = adapter_class(PkCity, engine)

    result = await adapter.get("garbage")

    assert result is None


@pytest.mark.anyio
async def test_get_related_with_garbage_key_returns_empty_list(
    engine: AsyncEngine, adapter_class: AdapterClass
) -> None:
    """A garbage (unparseable) pk also makes ``get_related`` return ``[]``, not raise."""
    adapter = adapter_class(PkCountry, engine)

    result = await adapter.get_related("garbage", "cities")

    assert result == []


# ---------------------------------------------------------------------------
# Scenario: update does not change the pk
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_does_not_change_pk(
    engine: AsyncEngine, city: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: update does not change the pk
      Given update data containing the pk attr
      When  adapter.update runs
      Then  the pk is unchanged
    """
    adapter = adapter_class(PkCity, engine)
    original_id = city.id
    spoofed_id = uuid.uuid4()

    updated = await adapter.update(pk=city.id, data={"name": "Greater London", "id": spoofed_id})

    assert updated is not None
    assert updated.id == original_id
    assert updated.name == "Greater London"

    reread = await adapter.get(original_id)
    assert reread is not None
    assert reread.id == original_id


# ---------------------------------------------------------------------------
# Scenario: UUID choice values
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_uuid_choice_values_are_canonical(
    engine: AsyncEngine, city: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: UUID choice values
      Given a UUID-keyed target model
      When  get_choices runs
      Then  option values are canonical UUID strings
    """
    adapter = adapter_class(PkCity, engine)

    choices = await adapter.get_choices("country")

    assert len(choices) == 1
    assert choices[0]["value"] == str(city.country_id)


# ---------------------------------------------------------------------------
# Scenario: UUID cascade filter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_uuid_cascade_filter_no_bind_error(
    engine: AsyncEngine, city: Any, country: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: UUID cascade filter
      Given a cascading filter country_id=<uuid str>
      When  get_choices runs
      Then  rows are filtered without bind errors
    """
    adapter = adapter_class(PkCountry, engine)

    choices = await adapter.get_choices("cities", country_id=str(country.id))

    assert len(choices) == 1
    assert choices[0]["label"] == "London"


# ---------------------------------------------------------------------------
# Scenario: pk 0 inline delete
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pk_zero_inline_delete(engine: AsyncEngine, adapter_class: AdapterClass) -> None:
    """
    Scenario: pk 0 inline delete
      Given an inline row with _pk=0 and _delete
      When  save_inline_rows runs
      Then  the delete is executed
    """
    widget_adapter = adapter_class(PkWidget, engine)
    widget = await widget_adapter.create({"name": "Gadget"})

    part_adapter = adapter_class(PkPart, engine)
    # An explicit pk=0 row — a truthiness check on ``_pk`` would wrongly treat
    # this row as having no key at all and skip the delete.
    await part_adapter.create({"id": 0, "sku": "bolt", "widget_id": widget.id})

    spec = InlineModelSpec(model=PkPart, fk_field="widget_id")
    await widget_adapter.save_inline_rows(spec, [{"_pk": 0, "_delete": True}], parent_pk=widget.id)

    remaining = await widget_adapter.inline_child_pks(spec, widget.id)
    assert remaining == set()


# ---------------------------------------------------------------------------
# Scenario: malformed UUID cascade filter returns no choices (review fix)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", ["", "garbage"])
@pytest.mark.anyio
async def test_malformed_uuid_cascade_filter_returns_empty_choices(
    engine: AsyncEngine, city: Any, adapter_class: AdapterClass, bad_value: str
) -> None:
    """
    Scenario: malformed UUID cascade filter returns no choices
      Given a UUID-keyed cascade filter (country_id)
      When  get_choices runs with an unparseable value ('' or 'garbage')
      Then  an empty choice list is returned instead of raising ValueError

    A dependent select sends '' while its parent select is still blank; an
    arbitrary 'garbage' query param is the hostile-input case. Before the fix,
    ``coerce_cascade_filter_value`` let ``uuid.UUID(raw)``'s ``ValueError``
    escape, turning ``GET /{model}/choices/cities?country_id=`` into a 500.
    """
    adapter = adapter_class(PkCountry, engine)

    choices = await adapter.get_choices("cities", country_id=bad_value)

    assert choices == []


# ---------------------------------------------------------------------------
# Scenario: UUID-keyed inline child is recognized as owned (review fix)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_uuid_keyed_inline_child_update_is_owned(
    engine: AsyncEngine, country: Any, city: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: UUID-keyed inline child update is recognized as owned
      Given a UUID-keyed child row already owned by the parent
      When  save_inline_rows submits an update with the child's string pk
      Then  the row updates without InlineRowNotOwnedError

    Before the fix, ``ensure_inline_rows_owned`` compared the submitted ``str``
    pk against the ``uuid.UUID`` instances ``inline_child_pks`` returns, so the
    sets never intersected and every update of an existing UUID-keyed inline
    child raised ``InlineRowNotOwnedError`` (404) — a save that touches no
    inline rows at all would never hit this, only one that edits an existing
    one.
    """
    country_adapter = adapter_class(PkCountry, engine)
    spec = InlineModelSpec(model=PkCity, fk_field="country_id")

    await country_adapter.save_inline_rows(
        spec,
        [{"_pk": str(city.id), "name": "Greater London"}],
        parent_pk=country.id,
    )

    city_adapter = adapter_class(PkCity, engine)
    updated = await city_adapter.get(city.id)
    assert updated is not None
    assert updated.name == "Greater London"


@pytest.mark.anyio
async def test_uuid_keyed_inline_child_delete_is_owned(
    engine: AsyncEngine, country: Any, city: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: UUID-keyed inline child delete is recognized as owned
      Given a UUID-keyed child row already owned by the parent
      When  save_inline_rows submits a delete with the child's string pk
      Then  the row is deleted without InlineRowNotOwnedError
    """
    country_adapter = adapter_class(PkCountry, engine)
    spec = InlineModelSpec(model=PkCity, fk_field="country_id")

    await country_adapter.save_inline_rows(
        spec,
        [{"_pk": str(city.id), "_delete": True}],
        parent_pk=country.id,
    )

    remaining = await country_adapter.inline_child_pks(spec, country.id)
    assert remaining == set()


@pytest.mark.anyio
async def test_unparseable_inline_pk_is_rejected_as_foreign(
    engine: AsyncEngine, country: Any, city: Any, adapter_class: AdapterClass
) -> None:
    """
    Scenario: unparseable inline pk is rejected as foreign
      Given a UUID-keyed inline child model
      When  save_inline_rows submits a non-UUID string as _pk
      Then  InlineRowNotOwnedError is raised (fails closed, not a 500)

    An unparseable submitted key can never be a real child row, so the fix
    treats the ``InvalidPrimaryKey`` from the child's pk codec as "foreign"
    instead of letting it propagate as an unhandled error.
    """
    country_adapter = adapter_class(PkCountry, engine)
    spec = InlineModelSpec(model=PkCity, fk_field="country_id")

    with pytest.raises(InlineRowNotOwnedError):
        await country_adapter.save_inline_rows(
            spec,
            [{"_pk": "not-a-uuid", "name": "Nowhere"}],
            parent_pk=country.id,
        )
