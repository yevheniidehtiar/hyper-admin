"""Regression guard and smoke test for the field-metadata seam (SDD sqlalchemy-field-metadata)."""

import ast
from pathlib import Path

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

import hyperadmin
from hyperadmin import Admin
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

SRC = Path(hyperadmin.__file__).parent

# Files that legitimately read Pydantic metadata directly: the seam itself, the SQLModel
# adapter, the Pydantic action forms, and the legacy static view (duck-typed models).
ALLOWED = {
    "core/schema.py",
    "adapters/schema.py",
    "adapters/sqlmodel.py",
    "views/dynamic/actions.py",
    "views/static.py",
}


def _is_schema_for_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "schema_for"
    )


def _violations(source: str) -> list[int]:
    """Line numbers of direct ``model_fields`` / ``<x>.model`` ``model_validate`` reads."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            if (node.attr == "model_fields" and not _is_schema_for_call(node.value)) or (
                node.attr == "model_validate" and ast.unparse(node.value).endswith(".model")
            ):
                lines.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "model_fields"
        ):
            lines.append(node.lineno)
    return sorted(lines)


def test_guard_flags_direct_reads_and_allows_schema_for() -> None:
    """
    Scenario: the guard distinguishes direct reads from the seam
      Given source with direct, getattr and model_validate reads plus schema_for reads
      When  the guard scans it
      Then  only the direct reads are reported
    """
    source = (
        "a = M.model_fields\n"
        "b = getattr(M, 'model_fields', {})\n"
        "c = self.model.model_validate(d)\n"
        "e = schema_for(M).model_fields\n"
        "f = schema_for(self.model).model_validate(d)\n"
        "g = getattr(M, 'other')\n"
    )
    assert _violations(source) == [1, 2, 3]


def test_no_direct_model_fields_reads_outside_the_seam() -> None:
    """
    Scenario: regression guard
      Given the source tree
      When  the guard scans src/hyperadmin for direct model_fields reads on admin models
      Then  only allow-listed files contain them
    """
    found = [
        f"{path.relative_to(SRC)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        if path.relative_to(SRC).as_posix() not in ALLOWED
        for line in _violations(path.read_text())
    ]
    assert not found, f"use schema_for(model) instead of reading the model directly: {found}"


class Base(DeclarativeBase):
    pass


class Widget(Base):
    __tablename__ = "seam_smoke_widget"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class WidgetAdmin(ModelAdmin):
    adapter_class = SQLAlchemyAdapter


@pytest.fixture
def seam_client():
    site._registry = {}
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(Widget(name="Alpha"))
            await session.commit()

    anyio.run(setup)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(Widget, WidgetAdmin)
    admin.mount(path="/admin")
    yield TestClient(app), engine
    site._registry = {}


def test_plain_declarative_model_list_and_create_form_return_200(seam_client) -> None:
    """
    Scenario: a plain DeclarativeBase model is served end to end
      Given a DeclarativeBase model "Widget" with one row
      When  its list page and create form are requested
      Then  both responses are 200 and the list shows the row
    """
    client, _ = seam_client
    listing = client.get("/admin/widget/")
    form = client.get("/admin/widget/create")
    assert listing.status_code == 200
    assert "Alpha" in listing.text
    assert form.status_code == 200
    assert 'name="name"' in form.text


def test_plain_declarative_model_create_inserts_a_row(seam_client) -> None:
    """
    Scenario: create saves through the adapter without model_validate
      Given a DeclarativeBase model "Widget"
      When  the create form is posted with a name
      Then  a row is inserted
    """
    client, engine = seam_client
    response = client.post(
        "/admin/widget",
        data={"name": "Beta"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 200

    async def names() -> list[str]:
        async with AsyncSession(engine) as session:
            return [w.name for w in (await session.execute(select(Widget))).scalars()]

    assert "Beta" in anyio.run(names)
