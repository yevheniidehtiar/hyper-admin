"""DynamicModelView wires the pk codec into its forms (st-v058-byoa-31, BYOA SDD A.6).

Create forms expose a natural (non-generated) key as an input; edit forms never
do. Inline formsets parse submitted child keys with the *inline* model's codec,
so UUID children update in place, malformed keys are row errors (422) and a
well-formed key that is not a child of the parent is still rejected (404) by
the adapter's ownership check.
"""

from __future__ import annotations

import uuid
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class FpkCountry(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    code: str = Field(primary_key=True)
    name: str = "country"


class FpkOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = "order"


class FpkLine(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID | None = Field(default=None, foreign_key="fpkorder.id")
    sku: str = ""


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


_LINES = InlineModelSpec(model=FpkLine, fk_field="order_id", fields=["sku"])


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with eng.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)
    return eng


def _seed(engine: Any, *rows: SQLModel) -> None:
    async def _add():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            for row in rows:
                session.add(row)
            await session.commit()

    anyio.run(_add)


def _all(engine: Any, model: type[SQLModel]) -> list[Any]:
    async def _fetch():
        async with AsyncSession(engine) as session:
            return list((await session.exec(select(model))).all())

    return anyio.run(_fetch)


def _mount(engine: Any, model: type[SQLModel], *, options: AdminOptions | None = None):
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(model, _Admin, options=options or AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app)


def test_create_form_offers_a_natural_pk_input(engine):
    """
    Scenario: natural pk on the create form
      Given a model with a natural str pk 'code'
      When  the create form is rendered
      Then  it has a 'code' input
    """
    client = _mount(engine, FpkCountry)

    response = client.get("/admin/fpkcountry/create")

    assert response.status_code == 200
    assert 'name="code"' in response.text


def test_create_view_stores_the_submitted_natural_pk(engine):
    """
    Scenario: natural pk create
      Given a model with a natural str pk 'code'
      When  the create form is submitted with code='007'
      Then  the row is stored under the str key '007'
    """
    client = _mount(engine, FpkCountry)

    response = client.post(
        "/admin/fpkcountry", data={"code": "007", "name": "Bond"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert [(r.code, r.name) for r in _all(engine, FpkCountry)] == [("007", "Bond")]


def test_create_view_requires_the_natural_pk(engine):
    """
    Scenario: natural pk is required on create
      Given a model with a natural str pk 'code'
      When  the create form is submitted without 'code'
      Then  the response is 422 and nothing is stored
    """
    client = _mount(engine, FpkCountry)

    response = client.post("/admin/fpkcountry", data={"name": "x"}, follow_redirects=False)

    assert response.status_code == 422
    assert _all(engine, FpkCountry) == []


def test_edit_form_hides_the_natural_pk(engine):
    """
    Scenario: natural pk is not editable
      Given a stored row with natural pk 'abc'
      When  its edit form is rendered
      Then  there is no 'code' input
    """
    _seed(engine, FpkCountry(code="abc", name="before"))
    client = _mount(engine, FpkCountry)

    response = client.get("/admin/fpkcountry/abc/edit")

    assert response.status_code == 200
    assert 'name="code"' not in response.text


def test_create_form_hides_a_generated_uuid_pk(engine):
    """
    Scenario: generated pk is not an input
      Given a model whose UUID pk is generated
      When  the create form is rendered
      Then  there is no 'id' input
    """
    client = _mount(engine, FpkOrder)

    response = client.get("/admin/fpkorder/create")

    assert response.status_code == 200
    assert 'name="id"' not in response.text


def _order_with_line(engine: Any) -> tuple[FpkOrder, FpkLine]:
    order = FpkOrder()
    line = FpkLine(order_id=order.id, sku="old")
    _seed(engine, order)
    _seed(engine, line)
    return order, line


def test_inline_uuid_pk_updates_that_child(engine):
    """
    Scenario: inline UUID pk
      Given an order with a UUID-keyed inline line
      When  the order is saved with the line's UUID string as '-pk'
      Then  that line is updated in place and no new line is created
    """
    order, line = _order_with_line(engine)
    client = _mount(engine, FpkOrder, options=AdminOptions(inlines=[_LINES]))

    response = client.put(
        f"/admin/fpkorder/{order.id}",
        data={"name": "o", "fpkline-0-pk": str(line.id).upper(), "fpkline-0-sku": "new"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert [(r.id, r.sku) for r in _all(engine, FpkLine)] == [(line.id, "new")]


def test_inline_invalid_pk_is_a_row_error(engine):
    """
    Scenario: inline invalid pk
      Given an order with a UUID-keyed inline line
      When  the order is saved with '-pk' = 'not-a-uuid'
      Then  the response is 422 and no line is written
    """
    order, line = _order_with_line(engine)
    client = _mount(engine, FpkOrder, options=AdminOptions(inlines=[_LINES]))

    response = client.put(
        f"/admin/fpkorder/{order.id}",
        data={"name": "o", "fpkline-0-pk": "not-a-uuid", "fpkline-0-sku": "new"},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert [(r.id, r.sku) for r in _all(engine, FpkLine)] == [(line.id, "old")]


def test_inline_foreign_uuid_pk_is_still_rejected(engine):
    """
    Scenario: a parsed pk is never trusted on its own
      Given two orders, each with one UUID-keyed line
      When  the first order is saved with the second order's line UUID as '-pk'
      Then  the response is 404 and the foreign line is unchanged
    """
    order, _line = _order_with_line(engine)
    _other, foreign = _order_with_line(engine)
    client = _mount(engine, FpkOrder, options=AdminOptions(inlines=[_LINES]))

    response = client.put(
        f"/admin/fpkorder/{order.id}",
        data={"name": "o", "fpkline-0-pk": str(foreign.id), "fpkline-0-sku": "stolen"},
        follow_redirects=False,
    )

    assert response.status_code == 404
    skus = {r.id: r.sku for r in _all(engine, FpkLine)}
    assert skus[foreign.id] == "old"
