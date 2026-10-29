"""Routing wraps adapters with the event-emitting proxy when enabled (#310)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.realtime import InMemoryPubSub, RealtimeSettings
from hyperadmin.realtime.emitting import EventEmittingAdapter, RealtimeEmitter
from hyperadmin.routing import HyperAdminRouter, create_admin_router


class RnGadget(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str


class RnSprocket(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def clean_registry():
    site._registry = {}
    yield
    site._registry = {}


def _emitter() -> RealtimeEmitter:
    return RealtimeEmitter(InMemoryPubSub(), "hyperadmin:")


def _view_adapter(router: object) -> object:
    route = next(r for r in router.routes if r.name == "rngadget-list")  # type: ignore[attr-defined]
    return route.endpoint.__self__.adapter


def _build(options: AdminOptions, **kwargs: object) -> object:
    site.register(RnGadget, _Admin, options=options)
    admin_class = site._registry[RnGadget]
    return create_admin_router(
        model=RnGadget,
        admin_class=admin_class,
        admin_instance=admin_class(RnGadget),
        options=options,
        engine=create_async_engine("sqlite+aiosqlite://"),
        templates=MagicMock(spec=Jinja2Templates),
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("global_on", "override", "wrapped"),
    [
        (True, None, True),
        (False, None, False),
        (False, True, True),
        (True, False, False),
    ],
)
def test_adapter_is_wrapped_only_when_enabled(
    global_on: bool, override: bool | None, wrapped: bool
) -> None:
    """
    Scenario: wrapping follows notifications_enabled
      Given an emitter and RealtimeSettings(notifications=<global_on>)
      And   a model with realtime_notifications=<override>
      When  the model router is created
      Then  the view adapter is an EventEmittingAdapter only when enabled
    """
    router = _build(
        AdminOptions(realtime_notifications=override),
        realtime_emitter=_emitter(),
        realtime_settings=RealtimeSettings(notifications=global_on),
    )
    assert isinstance(_view_adapter(router), EventEmittingAdapter) is wrapped


def test_adapter_not_wrapped_without_emitter() -> None:
    """
    Scenario: realtime off means no proxy
      Given no emitter (Admin(realtime=None))
      When  the model router is created
      Then  the view adapter is the plain adapter
    """
    router = _build(AdminOptions())
    assert isinstance(_view_adapter(router), SQLModelAdapter)


def test_info_logged_when_opt_in_but_realtime_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: per-model opt-in is ignored when realtime is off
      Given realtime is disabled and the model sets realtime_notifications=True
      When  the model router is created
      Then  an INFO log names the model
    """
    with caplog.at_level(logging.INFO):
        _build(AdminOptions(realtime_notifications=True))
    infos = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("RnGadget" in r.getMessage() for r in infos)


def test_router_records_notification_models(tmp_path: Path) -> None:
    """
    Scenario: HyperAdminRouter reports which models emit
      Given two registered models, one opted out
      When  routes are generated with an emitter
      Then  notification_models holds only the lowercased opted-in model name
    """
    site.register(RnGadget, _Admin, options=AdminOptions())
    site.register(
        RnSprocket,
        type("_SprocketAdmin", (_Admin,), {}),
        options=AdminOptions(realtime_notifications=False),
    )
    router = HyperAdminRouter(
        engine=create_async_engine("sqlite+aiosqlite://"),
        templates=Jinja2Templates(directory=str(tmp_path)),
        realtime_emitter=_emitter(),
        realtime_settings=RealtimeSettings(),
    )
    router.generate_routes()
    assert router.notification_models == {"rngadget"}


def test_router_notification_models_empty_without_emitter(tmp_path: Path) -> None:
    """
    Scenario: no emitter, no notification models
      Given a registered model and no emitter
      When  routes are generated
      Then  notification_models is empty
    """
    site.register(RnGadget, _Admin, options=AdminOptions())
    router = HyperAdminRouter(
        engine=create_async_engine("sqlite+aiosqlite://"),
        templates=Jinja2Templates(directory=str(tmp_path)),
    )
    router.generate_routes()
    assert router.notification_models == set()
