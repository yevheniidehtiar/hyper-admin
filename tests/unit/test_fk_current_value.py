"""The FK widget always carries the record's current value (st-ux-erp-02)."""

import re
from typing import Any
from unittest.mock import AsyncMock

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.dynamic.relations import RelationViewMixin

TARGETS = 60


class FkContact(SQLModel, table=True):
    __tablename__ = "test_fkcur_contact"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class FkInvoice(SQLModel, table=True):
    __tablename__ = "test_fkcur_invoice"
    id: int | None = Field(default=None, primary_key=True)
    number: str
    contact_id: int | None = Field(default=None, foreign_key="test_fkcur_contact.id")

    contact: Mapped[FkContact | None] = Relationship()


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine) as session:
            for i in range(1, TARGETS + 1):
                session.add(FkContact(id=i, name=f"Contact {i:02d}"))
            session.add(FkInvoice(id=1, number="INV-1", contact_id=TARGETS))
            await session.commit()

    anyio.run(setup)
    return engine


def _client(**options: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(app=app, engine=_engine(), settings=HyperAdminSettings(create_tables=False))
    contact_admin = type("FkContactAdmin", (ModelAdmin,), {"adapter_class": SQLModelAdapter})
    site.register(FkContact, contact_admin)
    site.register(
        FkInvoice,
        type(
            "FkInvoiceAdmin",
            (ModelAdmin,),
            {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def _probe(choices: list[Any]) -> RelationViewMixin:
    probe = RelationViewMixin.__new__(RelationViewMixin)
    probe.adapter = AsyncMock()  # type: ignore[attr-defined]
    probe.adapter.get_choices.return_value = choices  # type: ignore[attr-defined]
    probe._relation_target_for_field = lambda name: FkContact  # type: ignore[method-assign]
    probe._relation_label_fn = lambda name, rel: None  # type: ignore[method-assign]
    return probe


@pytest.mark.parametrize("autocomplete", [True, False])
def test_current_fk_value_is_shown_even_when_not_preloaded(autocomplete: bool) -> None:
    """
    Scenario: current FK value is shown even when not preloaded
      Given an invoice whose contact is the 60th of 60, past the 50-option window
      When  the user opens its edit page
      Then  the Contact field has that contact selected
    """
    body = _client(use_autocomplete_widget=autocomplete).get("/admin/fkinvoice/1/edit").text

    assert re.search(r'<option value="60"\s*selected>Contact 60</option>', body)
    assert body.count('<option value="60"') == 1


def test_preloaded_current_value_is_listed_once() -> None:
    """
    Scenario: a preloaded current value is listed once
      Given the stored contact is within the preload window
      When  the preload choices are built
      Then  that option appears exactly once, selected
    """
    probe = _probe([{"value": "5", "label": "Five", "selected": False}])

    result = anyio.run(probe._preload_choices, "contact_id", "contact", None, {"contact_id": 5})

    assert result == [{"value": "5", "label": "Five", "selected": True}]
    assert probe.adapter.get_choices.await_count == 1  # type: ignore[attr-defined]


def test_unreadable_current_value_falls_back_to_an_opaque_label() -> None:
    """
    Scenario: a current value the target query cannot return is still kept
      Given the stored contact is outside the target admin's scope
      When  the preload choices are built
      Then  the value is listed as "FkContact (<pk>)" and selected
    """
    probe = _probe([])

    result = anyio.run(probe._preload_choices, "contact_id", "contact", None, {"contact_id": 99})

    assert result == [{"value": "99", "label": "FkContact (99)", "selected": True}]


def test_empty_current_value_adds_nothing() -> None:
    """
    Scenario: a new record preloads only the window
      Given no current value
      When  the preload choices are built
      Then  no extra option is added
    """
    probe = _probe([{"value": "5", "label": "Five", "selected": False}])

    result = anyio.run(probe._preload_choices, "contact_id", "contact", None, {})

    assert result == [{"value": "5", "label": "Five", "selected": False}]


def test_current_value_label_follows_relation_display() -> None:
    """
    Scenario: the kept option is labelled like the rest of the list
      Given relation_display renders contacts upper-cased
      When  the edit page of an invoice with an out-of-window contact opens
      Then  the selected option carries the upper-cased label
    """
    client = _client(relation_display={"contact": lambda c: c.name.upper()})

    body = client.get("/admin/fkinvoice/1/edit").text

    assert re.search(r'<option value="60"\s*selected>CONTACT 60</option>', body)
