"""OCC configuration reaches the adapter through the router (SDD realtime-occ)."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

import hyperadmin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.concurrency import ConcurrencyConfigurationError
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.routing import create_admin_router

pytestmark = pytest.mark.anyio


class WiredOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    version: int = 1


class WiredTag(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


def _router_adapter(model: type, options: AdminOptions, engine: Any, **kwargs: Any) -> Any:
    seen: list[Any] = []

    class _Capturing(SQLModelAdapter):
        def __init__(self, *args: Any, **kw: Any) -> None:
            super().__init__(*args, **kw)
            seen.append(self)

    class _Admin(ModelAdmin):
        adapter_class = _Capturing
        app_label = None

    create_admin_router(
        model=model,
        admin_class=_Admin,
        admin_instance=_Admin(model),
        options=options,
        engine=engine,
        templates=MagicMock(spec=Jinja2Templates),
        **kwargs,
    )
    return seen[0]


@pytest.fixture
def engine() -> Any:
    return create_async_engine("sqlite+aiosqlite:///:memory:")


def test_enforce_occ_off_by_default(engine: Any) -> None:
    """
    Scenario: enforce_occ=False preserves legacy behaviour
      Given default AdminOptions
      Then  the adapter has no version field
    """
    assert AdminOptions().enforce_occ is False
    assert _router_adapter(WiredOrder, AdminOptions(), engine).version_field is None


def test_enforce_occ_sets_adapter_version_field(engine: Any) -> None:
    adapter = _router_adapter(WiredOrder, AdminOptions(enforce_occ=True), engine)
    assert adapter.version_field == "version"


def test_enforce_occ_without_version_field_fails_fast(engine: Any) -> None:
    """
    Scenario: no version field detected when neither is present
      When  a router is built for a model with enforce_occ=True and no version field
      Then  ConcurrencyConfigurationError is raised
    """
    with pytest.raises(ConcurrencyConfigurationError):
        _router_adapter(WiredTag, AdminOptions(enforce_occ=True), engine)


def test_settings_defaults_and_public_exports() -> None:
    settings = HyperAdminSettings()
    assert settings.concurrency_use_updated_at is False
    assert settings.occ_render_dialog is True
    assert hyperadmin.StaleRecordError.__name__ == "StaleRecordError"
    assert hyperadmin.ConcurrencyConfigurationError is ConcurrencyConfigurationError
