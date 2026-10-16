"""Enum members, empty values and optional fields as rendered by the admin pages.

Regression for the demo showing ``ContactType.CUSTOMER`` in list cells, the edit
form pre-selecting the first enum option instead of the stored one, and every
optional field carrying a required asterisk.
"""

import enum
import re

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class PartnerKind(str, enum.Enum):
    CUSTOMER = "Customer"
    SUPPLIER = "Supplier"


class EnumPartner(SQLModel, table=True):
    __tablename__ = "test_enum_partner"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str | None = None
    kind: PartnerKind = PartnerKind.CUSTOMER


class EnumPartnerAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["id", "name", "email", "kind"]


@pytest.fixture
def client():
    site._registry = {}
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine) as session:
            session.add(EnumPartner(name="Acme", kind=PartnerKind.SUPPLIER))
            await session.commit()

    anyio.run(seed)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(EnumPartner, EnumPartnerAdmin)
    admin.mount(path="/admin")
    yield TestClient(app)
    site._registry = {}


def test_list_cells_show_enum_labels_and_a_dash_for_empty_values(client: TestClient) -> None:
    """
    Scenario: list cells are human readable
      Given a partner of kind SUPPLIER with no email
      When  the partner list is opened
      Then  the kind cell reads "Supplier", never "PartnerKind.SUPPLIER"
      And   the empty email cell shows a dash instead of "None"
    """
    body = client.get("/admin/enumpartner").text

    assert "PartnerKind." not in body
    assert re.search(r'data-label="Kind">\s*Supplier\s*</td>', body)
    assert re.search(r'data-label="Email">\s*<span class="ha-text-muted">&mdash;</span>', body)
    assert ">None<" not in body


def test_detail_shows_the_enum_label(client: TestClient) -> None:
    """
    Scenario: detail page shows the enum label
      Given a partner of kind SUPPLIER
      When  its detail page is opened
      Then  the kind reads "Supplier"
    """
    body = client.get("/admin/enumpartner/1").text

    assert "PartnerKind." not in body
    assert re.search(r"<dd[^>]*>\s*Supplier\s*</dd>", body)


def test_edit_form_preselects_the_stored_choice_and_names_the_item(client: TestClient) -> None:
    """
    Scenario: edit form reflects the stored row
      Given a partner "Acme" of kind SUPPLIER with an optional email
      When  its edit form is opened
      Then  the title reads "Update Acme"
      And   the "Supplier" option is selected
      And   only the required name field carries an asterisk
    """
    body = client.get("/admin/enumpartner/1/edit").text

    assert re.search(r"Update\s+Acme", body)
    assert re.search(r'<option value="Supplier"\s*selected>Supplier</option>', body)
    assert not re.search(r'<option value="Customer"\s*selected', body)
    assert body.count('class="ha-required"') == 1
