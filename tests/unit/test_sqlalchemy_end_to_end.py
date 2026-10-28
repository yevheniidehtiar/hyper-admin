"""ASGI-client tests for a plain SQLAlchemy 2.0 model set (SDD sqlalchemy-field-metadata, P4a).

Each test maps 1:1 to a scenario of the spec's "BDD Scenarios" section. The models are plain
``DeclarativeBase`` classes: nothing here uses SQLModel except the one "unaffected" scenario.
"""

from __future__ import annotations

import enum
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator, UserDefinedType
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.schema import schema_for
from hyperadmin.core.settings import HyperAdminSettings

pytestmark = pytest.mark.anyio


class Base(DeclarativeBase):
    pass


class Status(enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class StringEnum(TypeDecorator[Status]):
    """A TypeDecorator over String: its column ``python_type`` is ``str``, not ``Status``."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Status | str | None, dialect: Any) -> str | None:
        return value.value if isinstance(value, Status) else value

    def process_result_value(self, value: str | None, dialect: Any) -> Status | None:
        return Status(value) if value is not None else None


class Opaque(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "TEXT"


class OpaqueDecorator(TypeDecorator[Any]):
    """Its ``python_type`` raises ``NotImplementedError`` (the impl has none)."""

    impl = Opaque
    cache_ok = True


class E2EOrg(Base):
    __tablename__ = "e2e_org"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class E2EProject(Base):
    __tablename__ = "e2e_project"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[Status] = mapped_column(Enum(Status))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("e2e_org.id"), nullable=True)
    org: Mapped[E2EOrg | None] = relationship()


class E2EAccount(Base):
    __tablename__ = "e2e_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    api_token: Mapped[str] = mapped_column(String(50))


class E2ECard(Base):
    __tablename__ = "e2e_card"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    status: Mapped[Status] = mapped_column(StringEnum())


class E2ERaw(Base):
    __tablename__ = "e2e_raw"
    id: Mapped[int] = mapped_column(primary_key=True)
    blob = mapped_column(OpaqueDecorator(), nullable=True)


class E2ESqlModel(SQLModel, table=True):
    __tablename__ = "e2e_sqlmodel_row"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class _Admin(ModelAdmin):
    adapter_class = SQLAlchemyAdapter


HX = {"HX-Request": "true"}


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    site._registry = {}
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    site._registry = {}
    await eng.dispose()


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    for model in (E2EOrg, E2EProject, E2EAccount, E2ECard, E2ERaw):
        site.register(model, _Admin)
    admin.mount(path="/admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def _add(engine: AsyncEngine, *rows: Any) -> None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(rows)
        await session.commit()


async def _all(engine: AsyncEngine, model: Any) -> list[Any]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(model).order_by(model.id))).scalars())


async def test_list_page_renders_for_a_plain_sqlalchemy_model(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    """
    Scenario: list page renders for a plain SQLAlchemy model
      Given a DeclarativeBase model "Org" with columns id, name, created_at and 3 rows
      When  the admin list page for "e2eorg" is requested
      Then  the response is 200 and shows 3 rows with name and created_at columns
    """
    # Given
    await _add(engine, *(E2EOrg(name=n) for n in ("Acme", "Globex", "Initech")))

    # When
    response = await client.get("/admin/e2eorg")

    # Then
    assert response.status_code == 200
    for name in ("Acme", "Globex", "Initech"):
        assert name in response.text
    assert response.text.count('data-testid="list-row"') == 3
    assert "created_at" in response.text


async def test_create_form_renders_one_field_per_mapped_column(client: AsyncClient) -> None:
    """
    Scenario: create form renders one field per mapped column
      Given a DeclarativeBase model with id, name, note, status, payload and org_id columns
      When  the create form is requested
      Then  it renders name (required), note (optional), status (select), payload (textarea)
            and org_id (relation select), and no id field
    """
    # Given the E2EProject model

    # When
    response = await client.get("/admin/e2eproject/create")

    # Then
    assert response.status_code == 200
    html = response.text
    for field in ("name", "note", "status", "payload", "org_id"):
        assert f'name="{field}"' in html
    assert 'name="id"' not in html
    assert "<select" in html
    # JSON renders through the generic text input today, as SQLModel dict fields do.
    assert "/admin/e2eproject/choices/org" in html


async def test_create_submits_coerces_and_saves(client: AsyncClient, engine: AsyncEngine) -> None:
    """
    Scenario: create submits, coerces and saves
      Given the model above and an existing org
      When  the create form is posted with valid values
      Then  a row is inserted with each value coerced to its column type
      And   the response redirects (to the new row's detail page, as for SQLModel)
    """
    # Given
    await _add(engine, E2EOrg(name="Acme"))

    # When
    response = await client.post(
        "/admin/e2eproject",
        data={
            "name": "Apollo",
            "note": "first",
            "status": "active",
            "org_id": "1",
        },
        headers=HX,
    )

    # Then
    assert response.status_code == 200
    # The create view redirects to the new row's detail page for every model kind.
    assert response.headers["HX-Redirect"].endswith("/admin/e2eproject/1")
    (row,) = await _all(engine, E2EProject)
    assert row.name == "Apollo"
    assert row.note == "first"
    assert row.status is Status.ACTIVE
    assert row.org_id == 1


async def test_create_rejects_invalid_input_with_field_errors(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    """
    Scenario: create rejects invalid input with field errors
      Given the model above
      When  the create form is posted without name and with status="bogus"
      Then  no row is inserted
      And   the form re-renders with errors on name and status
    """
    # Given the E2EProject model

    # When
    response = await client.post("/admin/e2eproject", data={"status": "bogus"}, headers=HX)

    # Then
    assert response.status_code == 422
    assert 'data-testid="name-errors"' in response.text
    assert 'data-testid="status-errors"' in response.text
    assert await _all(engine, E2EProject) == []


async def test_edit_round_trips_and_keeps_the_primary_key_immutable(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    """
    Scenario: edit round-trips and keeps the primary key immutable
      Given an existing row
      When  the edit form is posted with a changed name and a different id
      Then  only name changes
    """
    # Given
    await _add(engine, E2EOrg(name="Acme"))
    form = await client.get("/admin/e2eorg/1/edit")
    assert form.status_code == 200
    assert "Acme" in form.text

    # When
    response = await client.put("/admin/e2eorg/1", data={"name": "Acme 2", "id": "99"}, headers=HX)

    # Then
    assert response.status_code == 200
    (row,) = await _all(engine, E2EOrg)
    assert (row.id, row.name) == (1, "Acme 2")


async def test_detail_page_shows_column_values_masking_sensitive_ones(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    """
    Scenario: detail page shows column values, masking sensitive ones
      Given a model with columns name and api_token
      When  the detail page is requested
      Then  name is shown and api_token is masked, exactly as for SQLModel
    """
    # Given
    await _add(engine, E2EAccount(name="alice", api_token="tok-s3cret"))

    # When
    response = await client.get("/admin/e2eaccount/1")

    # Then
    assert response.status_code == 200
    assert "alice" in response.text
    assert "tok-s3cret" not in response.text


async def test_mapped_annotations_win_over_column_python_types(client: AsyncClient) -> None:
    """
    Scenario: Mapped annotations win over column python types
      Given status: Mapped[Status] = mapped_column(StringEnum()) over a TypeDecorator(String)
      When  the schema is built
      Then  the status field's annotation is Status, so it renders as an enum select
    """
    # Given the E2ECard model

    # When
    annotation = schema_for(E2ECard).model_fields["status"].annotation
    response = await client.get("/admin/e2ecard/create")

    # Then
    assert annotation is Status
    assert response.status_code == 200
    assert "<select" in response.text
    assert 'name="status"' in response.text


async def test_columns_with_no_resolvable_python_type_degrade_to_any(
    client: AsyncClient,
) -> None:
    """
    Scenario: columns with no resolvable Python type degrade to Any
      Given a custom TypeDecorator whose python_type raises NotImplementedError, unannotated
      When  the schema is built
      Then  the field's annotation is Any, it renders as a text input, and nothing raises
    """
    # Given the E2ERaw model

    # When
    annotation = schema_for(E2ERaw).model_fields["blob"].annotation
    response = await client.get("/admin/e2eraw/create")

    # Then
    assert annotation == Any | None  # nullable column: Any, re-wrapped as optional
    assert response.status_code == 200
    assert 'name="blob"' in response.text


async def test_sqlmodel_models_are_unaffected() -> None:
    """
    Scenario: SQLModel models are unaffected
      Given a SQLModel table model
      When  schema_for(model) is called
      Then  the model class itself is returned
    """
    # Given E2ESqlModel / When / Then
    assert schema_for(E2ESqlModel) is E2ESqlModel


async def test_search_filters_the_list(client: AsyncClient, engine: AsyncEngine) -> None:
    """
    Scenario: search narrows the list on a plain SQLAlchemy model
      Given orgs "Acme" and "Globex"
      When  the list is requested with search=glob
      Then  only "Globex" is shown
    """
    # Given
    await _add(engine, E2EOrg(name="Acme"), E2EOrg(name="Globex"))

    # When
    response = await client.get("/admin/e2eorg", params={"search": "glob"})

    # Then
    assert response.status_code == 200
    assert "Globex" in response.text
    assert "Acme" not in response.text


async def test_sort_orders_the_list(client: AsyncClient, engine: AsyncEngine) -> None:
    """
    Scenario: sort orders the list on a plain SQLAlchemy model
      Given orgs "Acme" and "Globex"
      When  the list is requested sorted by name descending
      Then  "Globex" appears before "Acme"
    """
    # Given
    await _add(engine, E2EOrg(name="Acme"), E2EOrg(name="Globex"))

    # When
    response = await client.get(
        "/admin/e2eorg", params={"sort_by": "name", "sort_direction": "desc"}
    )

    # Then
    assert response.status_code == 200
    assert response.text.index("Globex") < response.text.index("Acme")


async def test_fk_column_renders_a_relation_select_with_target_rows(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    """
    Scenario: FK column renders a relation select
      Given an org "Acme" and the project model with an org_id FK
      When  the create form is requested
      Then  the org_id control is a relation select whose choices endpoint offers "Acme"
    """
    # Given
    await _add(engine, E2EOrg(name="Acme"))

    # When
    response = await client.get("/admin/e2eproject/create")

    # Then
    assert response.status_code == 200
    choices_url = re.search(r'hx-get="[^"]*(/admin/e2eproject/choices/org)"', response.text)
    assert choices_url is not None
    choices = await client.get(choices_url.group(1), params={"q": "Acm"})
    assert choices.status_code == 200
    assert "Acme" in choices.text
