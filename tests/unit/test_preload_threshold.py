"""Large foreign-key targets fall back from preloaded options to autocomplete (#213)."""

import re
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

TARGETS = 20


class PtCountry(SQLModel, table=True):
    __tablename__ = "test_ptcountry"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class PtTrip(SQLModel, table=True):
    __tablename__ = "test_pttrip"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    origin_id: int | None = Field(default=None, foreign_key="test_ptcountry.id")
    destination_id: int | None = Field(default=None, foreign_key="test_ptcountry.id")

    origin: Mapped[PtCountry | None] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[PtTrip.origin_id]"}
    )
    destination: Mapped[PtCountry | None] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[PtTrip.destination_id]"}
    )


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
                session.add(PtCountry(id=i, name=f"Country {i:02d}"))
            session.add(PtTrip(id=1, title="Trip", origin_id=1, destination_id=2))
            await session.commit()

    anyio.run(setup)
    return engine


def _client(**options: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(app=app, engine=_engine(), settings=HyperAdminSettings(create_tables=False))
    site.register(
        PtCountry, type("PtCountryAdmin", (ModelAdmin,), {"adapter_class": SQLModelAdapter})
    )
    site.register(
        PtTrip,
        type(
            "PtTripAdmin",
            (ModelAdmin,),
            {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def test_preload_threshold_defaults_to_500() -> None:
    """
    Scenario: the threshold defaults to 500 rows
      Given AdminOptions without a preload_threshold
      When  the options are read
      Then  preload_threshold is 500
    """
    assert AdminOptions().preload_threshold == 500


def test_preload_threshold_rejects_a_negative_value() -> None:
    """
    Scenario: a negative threshold is rejected
      Given a preload_threshold of -1
      When  AdminOptions is built
      Then  validation fails
    """
    with pytest.raises(ValidationError):
        AdminOptions(preload_threshold=-1)


def test_small_target_table_preloads_inline() -> None:
    """
    Scenario: small FK target table preloads inline
      Given a 20-row Country table and the default threshold of 500
      When  the trip create form is rendered
      Then  every country is an option in the page
    """
    body = _client().get("/admin/pttrip/create").text

    assert "Country 01" in body
    assert f"Country {TARGETS:02d}" in body


def test_large_target_table_downgrades_to_autocomplete() -> None:
    """
    Scenario: large FK target table downgrades to HTMX autocomplete
      Given a 20-row Country table and preload_threshold = 10
      When  the trip create form is rendered
      Then  no country is listed as an option
      And   the widget fetches its options from the choices endpoint
    """
    body = _client(preload_threshold=10).get("/admin/pttrip/create").text

    assert "Country 01" not in body
    assert "/pttrip/choices/origin" in body


def test_downgraded_field_still_shows_the_stored_value() -> None:
    """
    Scenario: a downgraded field keeps the stored value selected
      Given a Country table over the threshold and a trip from country 1 to country 2
      When  the trip edit form is rendered
      Then  the origin and destination options are selected
      And   no other country is listed
    """
    body = _client(preload_threshold=10).get("/admin/pttrip/1/edit").text

    assert re.search(r'<option value="1"\s*selected>', body)
    assert re.search(r'<option value="2"\s*selected>', body)
    assert "Country 05" not in body


def test_none_threshold_keeps_every_option_preloaded() -> None:
    """
    Scenario: opting out preserves the pre-0.7 behaviour
      Given preload_threshold = None on a table larger than any threshold
      When  the trip create form is rendered
      Then  every country is an option in the page
    """
    body = _client(preload_threshold=None).get("/admin/pttrip/create").text

    assert f"Country {TARGETS:02d}" in body


def test_none_threshold_never_estimates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: opting out issues no estimate query
      Given preload_threshold = None
      When  the trip create form is rendered
      Then  estimate_row_count is never called
    """
    calls: list[int] = []

    async def estimate(self: SQLModelAdapter) -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(SQLModelAdapter, "estimate_row_count", estimate)

    _client(preload_threshold=None).get("/admin/pttrip/create")

    assert calls == []


def test_adapter_without_an_estimate_falls_back_to_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: an adapter without estimate_row_count falls back to preload
      Given an adapter whose estimate_row_count raises NotImplementedError
      When  the trip create form is rendered
      Then  the request succeeds
      And   every country is still an option
    """

    async def unsupported(self: SQLModelAdapter) -> int:
        raise NotImplementedError

    monkeypatch.setattr(SQLModelAdapter, "estimate_row_count", unsupported)

    resp = _client(preload_threshold=10).get("/admin/pttrip/create")

    assert resp.status_code == 200
    assert f"Country {TARGETS:02d}" in resp.text


def test_estimate_is_taken_once_per_target_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: one estimate per target table per request
      Given a trip with two foreign keys to Country
      When  the trip create form is rendered
      Then  estimate_row_count runs once
    """
    calls: list[int] = []
    original = SQLModelAdapter.estimate_row_count

    async def counted(self: SQLModelAdapter) -> int:
        calls.append(1)
        return await original(self)

    monkeypatch.setattr(SQLModelAdapter, "estimate_row_count", counted)

    _client(preload_threshold=10).get("/admin/pttrip/create")

    assert calls == [1]
