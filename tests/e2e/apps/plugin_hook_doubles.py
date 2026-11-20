"""Shared plugin doubles for the plugin-hook E2E suite (``_plugin_fixtures`` in the story).

The admin under test runs in a uvicorn subprocess, so a test cannot reach into it.
``RecordingPlugin`` therefore exposes what it saw over a plugin page
(``GET /admin/recording/events``) and ``BrokenPlugin`` raises from every hook;
the app module (:mod:`tests.e2e.apps.plugin_hooks`) hands both to
:func:`install_entry_points`, which stands in for installed packages by patching
the registry's ``entry_points`` lookup (the subprocess equivalent of a pytest
``monkeypatch``).
"""

from __future__ import annotations

import logging
from importlib.metadata import EntryPoint
from typing import Any

from fastapi import APIRouter

from hyperadmin.core import plugins as plugins_module

_HOOKS = (
    "on_before_create",
    "on_after_create",
    "on_before_update",
    "on_after_update",
    "on_before_delete",
    "on_after_delete",
    "on_before_adapter_call",
    "on_after_adapter_call",
)


class RecordingPlugin:
    """Records every lifecycle hook it receives and serves the record as JSON."""

    name = "recording"

    def __init__(self) -> None:
        self.register_calls = 0
        self.events: list[dict[str, str]] = []

    def on_register(self, admin: Any) -> None:
        self.register_calls += 1
        router = APIRouter()

        @router.get("/events", name="recording-events")
        async def events() -> dict[str, Any]:
            return {"register_calls": self.register_calls, "events": self.events}

        admin.plugins.add_page(self, router)

    def _record(self, hook: str, **kwargs: Any) -> None:
        model = kwargs.get("model")
        self.events.append(
            {"hook": hook, "model": getattr(model, "__name__", ""), "op": str(kwargs.get("op", ""))}
        )

    def on_before_create(self, **kw: Any) -> None:
        self._record("on_before_create", **kw)

    def on_after_create(self, **kw: Any) -> None:
        self._record("on_after_create", **kw)

    def on_before_update(self, **kw: Any) -> None:
        self._record("on_before_update", **kw)

    def on_after_update(self, **kw: Any) -> None:
        self._record("on_after_update", **kw)

    def on_before_delete(self, **kw: Any) -> None:
        self._record("on_before_delete", **kw)

    def on_after_delete(self, **kw: Any) -> None:
        self._record("on_after_delete", **kw)

    def on_before_adapter_call(self, **kw: Any) -> None:
        self._record("on_before_adapter_call", **kw)

    def on_after_adapter_call(self, **kw: Any) -> None:
        self._record("on_after_adapter_call", **kw)


class BrokenPlugin:
    """Raises from every lifecycle hook; the request must still succeed."""

    name = "broken"

    def on_register(self, admin: Any) -> None:
        router = APIRouter()

        @router.get("/logs", name="broken-logs")
        async def logs() -> dict[str, list[str]]:
            return {"messages": _LOG_CAPTURE.messages}

        admin.plugins.add_page(self, router)


def _raise(self: BrokenPlugin, **_kwargs: Any) -> None:
    raise RuntimeError("broken plugin hook")


for _hook in _HOOKS:
    setattr(BrokenPlugin, _hook, _raise)


class _LogCapture(logging.Handler):
    """Collects the registry's error logs so the broken plugin's page can serve them."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


_LOG_CAPTURE = _LogCapture()


def install_entry_points(plugins: dict[str, Any], *, disabled_name: str) -> None:
    """Make the registry discover ``plugins`` plus one extra entry point to be disabled.

    ``plugins`` maps entry-point name to the plugin instance; the loader is the
    patched ``EntryPoint.load`` so no real distribution is needed.
    """
    logging.getLogger(plugins_module.__name__).addHandler(_LOG_CAPTURE)
    group = plugins_module.PLUGIN_ENTRY_POINT_GROUP
    eps = [
        EntryPoint(name=n, value=f"fake_pkg:{n}", group=group) for n in (*plugins, disabled_name)
    ]
    loaded = {f"fake_pkg:{n}": p for n, p in plugins.items()}
    loaded[f"fake_pkg:{disabled_name}"] = RecordingPlugin()

    def _load(self: EntryPoint) -> Any:
        return loaded[self.value]

    EntryPoint.load = _load  # type: ignore[method-assign]
    plugins_module.entry_points = lambda **_kw: eps  # type: ignore[assignment]
