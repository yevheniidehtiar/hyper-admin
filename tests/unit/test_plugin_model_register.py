"""``on_model_register`` fires from ``SiteRegistry.register`` (SDD ``docs/specs/plugin-registry.md``)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import SiteRegistry, site
from hyperadmin.core.settings import HyperAdminSettings
from tests.unit.test_plugin_wiring import _install


class HookProduct(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


class HookCategory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


@pytest.fixture(autouse=True)
def _clean_site() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved
    site._hook_dispatcher = None


def test_on_model_register_fires_once_per_registered_model() -> None:
    """
    Scenario: on_model_register fires for each registered model
      Given a dispatcher attached to a registry
      When  two models are registered
      Then  each model is dispatched exactly once, with its options
    """
    registry = SiteRegistry()
    calls: list[tuple[str, dict[str, Any]]] = []
    registry.attach_hook_dispatcher(lambda hook, **kw: calls.append((hook, kw)))
    options = AdminOptions(can_delete=False)

    registry.register(HookProduct, options=options)
    registry.register(HookCategory)

    assert [(hook, kw["model"]) for hook, kw in calls] == [
        ("on_model_register", HookProduct),
        ("on_model_register", HookCategory),
    ]
    assert calls[0][1]["options"] is options


def test_on_model_register_fires_after_the_admin_class_is_stored() -> None:
    """
    Scenario: on_model_register fires after adapter is attached
      Given a dispatcher that reads the registry while it runs
      When  a model is registered
      Then  the stored admin class already has its adapter and options
    """
    registry = SiteRegistry()
    seen: list[Any] = []

    def dispatcher(hook: str, **kw: Any) -> None:
        admin_class = registry._registry[kw["model"]]
        seen.append((admin_class.adapter_class, admin_class.options))

    registry.attach_hook_dispatcher(dispatcher)
    registry.register(HookProduct)

    assert len(seen) == 1
    assert seen[0][0] is not None
    assert seen[0][1] is not None


def test_on_model_register_does_not_fire_for_a_duplicate_registration() -> None:
    """
    Scenario: duplicate registration does not fire the hook
      Given a registered model
      When  the same model is registered again
      Then  ValueError is raised and the hook fired only once
    """
    registry = SiteRegistry()
    calls: list[Any] = []
    registry.attach_hook_dispatcher(lambda hook, **kw: calls.append(kw["model"]))
    registry.register(HookProduct)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(HookProduct)

    assert calls == [HookProduct]


def test_attach_replays_models_registered_before_the_dispatcher() -> None:
    """
    Scenario: models registered at import time are announced on attach
      Given a model registered before any admin mounted
      When  a dispatcher is attached
      Then  the hook fires once for that model, and detaching stops further calls
    """
    registry = SiteRegistry()
    registry.register(HookProduct)
    calls: list[Any] = []

    registry.attach_hook_dispatcher(lambda hook, **kw: calls.append(kw["model"]))
    registry.attach_hook_dispatcher(None)
    registry.register(HookCategory)

    assert calls == [HookProduct]


def test_mounted_admin_delivers_on_model_register_to_plugins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a plugin hears about models through Admin.mount
      Given a plugin recording on_model_register, and a model registered before mount
      When  the admin mounts and another model is registered
      Then  the plugin saw both models, each with admin= the Admin
    """
    calls: list[dict[str, Any]] = []

    class _Recorder:
        name = "recorder"

        def on_register(self, admin: Any) -> None:
            pass

        def on_model_register(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    _install(monkeypatch, recorder=_Recorder)
    site.register(HookProduct)
    admin = Admin(
        FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(create_tables=False, secret_key="x" * 40),
    )

    admin.mount("/admin")
    site.register(HookCategory)

    assert [c["model"] for c in calls] == [HookProduct, HookCategory]
    assert all(c["admin"] is admin for c in calls)
