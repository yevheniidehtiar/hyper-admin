"""Unit tests for ``hyperadmin.core.plugins`` (SDD ``docs/specs/plugin-registry.md``)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from hyperadmin.core import plugins as plugins_mod
from hyperadmin.core.plugins import (
    DISABLED_PLUGINS_ENV,
    NavEntry,
    Plugin,
    PluginError,
    PluginRegistry,
    parse_disabled_env,
)

ADMIN = object()


@dataclass
class FakeEntryPoint:
    name: str
    value: str
    target: Callable[[], Any]

    def load(self) -> Any:
        return self.target()


class RecordingPlugin:
    def __init__(self, name: str = "demo", setup: Callable[[Any], None] | None = None) -> None:
        self.name = name
        self.setup = setup
        self.registered_with: list[Any] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def on_register(self, admin: Any) -> None:
        self.registered_with.append(admin)
        if self.setup is not None:
            self.setup(self)

    def on_after_create(self, **kwargs: Any) -> None:
        self.calls.append(("on_after_create", kwargs))


def _install(monkeypatch: pytest.MonkeyPatch, *eps: FakeEntryPoint) -> None:
    def fake_entry_points(*, group: str) -> list[FakeEntryPoint]:
        assert group == "hyperadmin.plugins"
        return list(eps)

    monkeypatch.setattr(plugins_mod, "entry_points", fake_entry_points)
    monkeypatch.delenv(DISABLED_PLUGINS_ENV, raising=False)


def _ep(name: str, plugin: Any, value: str | None = None) -> FakeEntryPoint:
    return FakeEntryPoint(name, value or f"pkg_{name}:Plugin", lambda: plugin)


def _registered(plugin: Any) -> PluginRegistry:
    registry = PluginRegistry()
    assert registry.register(plugin, admin=ADMIN)
    return registry


# -- protocol & discovery -------------------------------------------------------


def test_protocol_is_runtime_checkable() -> None:
    """
    Scenario: protocol is runtime-checkable
      Given a class with name and on_register
      When  isinstance(instance, Plugin) is evaluated
      Then  the result is True, and False for an object without on_register
    """
    assert isinstance(RecordingPlugin(), Plugin)
    assert not isinstance(object(), Plugin)


def test_registry_is_empty_without_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: registry is empty by default
      Given no entry points exist for "hyperadmin.plugins"
      When  PluginRegistry.discover is called
      Then  names() is empty and the registry is falsy
    """
    _install(monkeypatch)
    registry = PluginRegistry.discover(admin=ADMIN)
    assert registry.names() == []
    assert not registry
    assert len(registry) == 0


def test_discover_registers_plugin_classes_and_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: plugin discovered via entry point
      Given entry points for a plugin class and a plugin instance
      When  discover runs
      Then  both are registered in name order and on_register got the admin once
    """
    instance = RecordingPlugin("beta")

    class Alpha(RecordingPlugin):
        def __init__(self) -> None:
            super().__init__("alpha")

    _install(
        monkeypatch,
        _ep("beta", instance),
        FakeEntryPoint("alpha", "pkg_alpha:Alpha", lambda: Alpha),
    )
    registry = PluginRegistry.discover(admin=ADMIN)

    assert registry.names() == ["alpha", "beta"]
    assert "beta" in registry
    assert registry["beta"] is instance
    assert instance.registered_with == [ADMIN]
    assert isinstance(registry["alpha"], Alpha)
    assert registry.origin("alpha") == "pkg_alpha:Alpha"


def test_disabled_plugins_union_ctor_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: disabled plugin is not loaded
      Given three plugins, one disabled in code and one via the env var
      When  discover runs
      Then  only the third is registered and the others are reported as disabled
    """
    a, b, c = RecordingPlugin("a"), RecordingPlugin("b"), RecordingPlugin("c")
    _install(monkeypatch, _ep("a", a), _ep("b", b), _ep("c", c))
    monkeypatch.setenv(DISABLED_PLUGINS_ENV, " b, ,")

    registry = PluginRegistry.discover(admin=ADMIN, disabled=["a", "nonexistent"])

    assert registry.names() == ["c"]
    assert a.registered_with == [] and b.registered_with == []
    assert registry.skipped == {"a": "disabled", "b": "disabled"}


def test_parse_disabled_env() -> None:
    """
    Scenario: malformed env var
      Given empty, missing and padded values
      Then  blank tokens are dropped and names are stripped
    """
    assert parse_disabled_env(None) == set()
    assert parse_disabled_env("") == set()
    assert parse_disabled_env(" x ,,y,") == {"x", "y"}


def test_duplicate_entry_point_name_keeps_first(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: two distributions expose the same plugin name
      When  discover runs
      Then  the first by (name, value) wins and the second logs a WARNING
    """
    first, second = RecordingPlugin(), RecordingPlugin()
    _install(monkeypatch, _ep("demo", second, "z_pkg:P"), _ep("demo", first, "a_pkg:P"))
    with caplog.at_level(logging.WARNING, logger="hyperadmin.core.plugins"):
        registry = PluginRegistry.discover(admin=ADMIN)

    assert registry["demo"] is first
    assert second.registered_with == []
    assert any(r.levelno == logging.WARNING and "z_pkg:P" in r.getMessage() for r in caplog.records)


def test_broken_and_invalid_entry_points_are_isolated(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: plugin import raises / object is not a plugin
      Given a broken import, a non-plugin object, a name mismatch and a good plugin
      When  discover runs
      Then  only the good plugin loads and each failure is logged at ERROR
    """

    def boom() -> Any:
        raise ImportError("missing optional dep")

    good = RecordingPlugin("good")
    _install(
        monkeypatch,
        FakeEntryPoint("broken", "pkg:Broken", boom),
        _ep("notaplugin", object()),
        _ep("mismatch", RecordingPlugin("other")),
        _ep("good", good),
    )
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugins"):
        registry = PluginRegistry.discover(admin=ADMIN)

    assert registry.names() == ["good"]
    assert registry.skipped == {
        "broken": "load_error",
        "notaplugin": "invalid",
        "mismatch": "invalid",
    }
    assert {getattr(r, "plugin", None) for r in caplog.records} >= {
        "broken",
        "notaplugin",
        "mismatch",
    }


def test_on_register_failure_rolls_back_contributions(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: plugin on_register raises
      Given a plugin that adds a permission and then raises
      When  it is registered
      Then  it is not kept, its permission is gone and an ERROR names the hook
    """

    def setup(p: Any) -> None:
        registry.add_permission(p, "view_thing")
        raise RuntimeError("bad")

    registry = PluginRegistry()
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugins"):
        assert not registry.register(RecordingPlugin(setup=setup), admin=ADMIN)

    assert "demo" not in registry
    assert registry.permissions == []
    assert registry.skipped == {"demo": "register_error"}
    assert caplog.records[-1].hook == "on_register"  # type: ignore[attr-defined]
    # The name is free again: a fixed plugin can register.
    assert registry.register(RecordingPlugin(), admin=ADMIN)


@pytest.mark.parametrize("name", ["", "Bad Name", "1abc", 3])
def test_register_rejects_invalid_names(name: Any) -> None:
    """
    Scenario: plugin name is not URL-safe
      Then  register returns False and nothing is kept
    """
    registry = PluginRegistry()
    plugin = RecordingPlugin()
    plugin.name = name
    assert not registry.register(plugin, admin=ADMIN)
    assert plugin.registered_with == []


def test_register_rejects_duplicate_name() -> None:
    """
    Scenario: the same name is registered twice manually
      Then  the second registration is refused
    """
    registry = _registered(RecordingPlugin())
    assert not registry.register(RecordingPlugin(), admin=ADMIN)


def test_manual_register_origin_defaults_to_class_path() -> None:
    """
    Scenario: plugin registered without an entry point
      Then  its origin is its class import path
    """
    registry = _registered(RecordingPlugin())
    assert registry.origin("demo") == f"{__name__}:RecordingPlugin"


# -- typed settings ---------------------------------------------------------------


class ReportSettings(BaseModel):
    page_size: int = 50
    cache: bool = False


class SettingsPlugin(RecordingPlugin):
    settings_model = ReportSettings


def test_settings_are_validated_before_on_register() -> None:
    """
    Scenario: typed plugin settings
      Given a plugin with a settings_model and operator settings
      When  it is registered
      Then  on_register can already read the validated settings instance
    """
    registry = PluginRegistry()
    seen: list[Any] = []
    plugin = SettingsPlugin(setup=lambda p: seen.append(registry.settings("demo")))

    assert registry.register(plugin, admin=ADMIN, settings={"page_size": "10"})

    assert seen == [ReportSettings(page_size=10)]
    assert registry.settings("unknown") is None


def test_discover_passes_settings_per_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: settings for discovered plugins
      Given settings keyed by plugin name, including one for an absent plugin
      Then  the discovered plugin receives its own settings
    """
    _install(monkeypatch, _ep("demo", SettingsPlugin()))
    registry = PluginRegistry.discover(
        admin=ADMIN, settings={"demo": {"cache": True}, "absent": {"x": 1}}
    )
    assert registry.settings("demo") == ReportSettings(cache=True)


def test_settings_default_and_invalid() -> None:
    """
    Scenario: settings omitted / invalid
      Then  defaults apply when omitted, and invalid settings skip the plugin
    """
    registry = _registered(SettingsPlugin())
    assert registry.settings("demo") == ReportSettings()

    other = PluginRegistry()
    assert not other.register(SettingsPlugin(), admin=ADMIN, settings={"page_size": "x"})
    assert other.settings("demo") is None


# -- UI seams ---------------------------------------------------------------------


def test_ui_seams_are_collected(tmp_path: Path) -> None:
    """
    Scenario: plugin contributes pages, nav, templates, static and permissions
      Given a plugin that uses every seam in on_register
      When  it is registered
      Then  the registry exposes each contribution attributed to the plugin
    """
    router = APIRouter()
    templates = tmp_path / "templates"
    static = tmp_path / "static"
    templates.mkdir()
    static.mkdir()
    registry = PluginRegistry()

    def setup(p: Any) -> None:
        registry.add_page(p, router)
        registry.add_page(p, APIRouter(), prefix="/reports/api")
        registry.add_nav_entry(p, label="Reports", url_name="reports-index", icon="chart")
        registry.add_template_dir(p, templates)
        registry.set_static_dir(p, static)
        registry.add_permission(p, "view_report_sales")
        registry.add_permission(p, "export_report", "Can export reports")

    assert registry.register(RecordingPlugin("reports", setup=setup), admin=ADMIN)

    assert [(pg.prefix, pg.plugin) for pg in registry.pages] == [
        ("/reports", "reports"),
        ("/reports/api", "reports"),
    ]
    assert registry.pages[0].router is router
    assert registry.nav_entries == [
        NavEntry(plugin="reports", label="Reports", url_name="reports-index", icon="chart")
    ]
    assert [d.path for d in registry.template_dirs] == [templates.resolve()]
    (static_dir,) = registry.static_dirs
    assert static_dir.mount_path == "/static/plugins/reports"
    assert static_dir.path == static.resolve()
    assert [(p.codename, p.name) for p in registry.permissions] == [
        ("view_report_sales", "Can view report sales"),
        ("export_report", "Can export reports"),
    ]


def test_nav_entries_are_ordered_by_order_then_label() -> None:
    """
    Scenario: deterministic nav ordering
      Given two plugins adding entries with different orders
      Then  entries sort by (order, label)
    """
    registry = PluginRegistry()

    def first(p: Any) -> None:
        registry.add_nav_entry(p, label="Zeta", url_name="z", order=1)
        registry.add_nav_entry(p, label="Beta", url_name="b", order=1, url_params={"k": 1})

    def second(p: Any) -> None:
        registry.add_nav_entry(p, label="Omega", url_name="o", order=0, section="Data")

    registry.register(RecordingPlugin("one", setup=first), admin=ADMIN)
    registry.register(RecordingPlugin("two", setup=second), admin=ADMIN)

    assert [e.label for e in registry.nav_entries] == ["Omega", "Beta", "Zeta"]
    assert registry.nav_entries[1].url_params == {"k": 1}


def test_static_dirs_skip_plugins_without_one() -> None:
    """
    Scenario: plugin without static files
      Then  static_dirs is empty
    """
    assert _registered(RecordingPlugin()).static_dirs == []


def test_seams_outside_on_register_raise() -> None:
    """
    Scenario: seam called after registration or by another plugin
      Then  PluginError is raised
    """
    plugin = RecordingPlugin()
    registry = _registered(plugin)
    with pytest.raises(PluginError, match="own on_register"):
        registry.add_permission(plugin, "view_x")

    def setup(p: Any) -> None:
        registry.add_permission(plugin, "view_y")

    assert not registry.register(RecordingPlugin("intruder", setup=setup), admin=ADMIN)


def _failing_seam(call: Callable[[PluginRegistry, Any], Any]) -> str:
    """Register a plugin whose seam call fails; return the error message."""
    registry = PluginRegistry()
    errors: list[str] = []

    def setup(p: Any) -> None:
        try:
            call(registry, p)
        except PluginError as exc:
            errors.append(str(exc))
            raise

    assert not registry.register(RecordingPlugin("subject", setup=setup), admin=ADMIN)
    return errors[0]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda r, p: r.add_page(p, APIRouter(), prefix="reports"), "invalid page prefix"),
        (lambda r, p: r.add_page(p, APIRouter(), prefix="/x/"), "invalid page prefix"),
        (lambda r, p: r.add_page(p, object()), "is not a router"),
        (lambda r, p: r.add_nav_entry(p, label="", url_name="x"), "needs a label"),
        (lambda r, p: r.add_nav_entry(p, label="X", url_name=""), "needs a label"),
        (lambda r, p: r.add_template_dir(p, "/nonexistent/dir"), "does not exist"),
        (lambda r, p: r.set_static_dir(p, "/nonexistent/dir"), "does not exist"),
        (lambda r, p: r.add_permission(p, "View Report"), "invalid permission codename"),
    ],
)
def test_seam_argument_validation(call: Callable[..., Any], message: str) -> None:
    """
    Scenario: seam called with an invalid argument
      Then  PluginError is raised inside on_register and the plugin is skipped
    """
    assert message in _failing_seam(call)


def test_second_static_dir_is_rejected(tmp_path: Path) -> None:
    """
    Scenario: plugin sets two static dirs
      Then  the second call raises
    """

    def call(r: PluginRegistry, p: Any) -> None:
        r.set_static_dir(p, tmp_path)
        r.set_static_dir(p, tmp_path)

    assert "already has a static dir" in _failing_seam(call)


def test_page_prefix_and_permission_conflicts_across_plugins() -> None:
    """
    Scenario: two plugins claim the same page prefix or permission codename
      Then  the later plugin fails to register
    """

    registry = PluginRegistry()

    def prior(p: Any) -> None:
        registry.add_page(p, APIRouter(), prefix="/shared")

    registry.register(RecordingPlugin("first", setup=prior), admin=ADMIN)

    def dup_page(p: Any) -> None:
        registry.add_page(p, APIRouter(), prefix="/shared")

    def dup_perm(p: Any) -> None:
        registry.add_permission(p, "view_one")
        registry.add_permission(p, "view_one")

    assert not registry.register(RecordingPlugin("second", setup=dup_page), admin=ADMIN)
    assert not registry.register(RecordingPlugin("third", setup=dup_perm), admin=ADMIN)
    assert registry.names() == ["first"]


# -- hook dispatch ----------------------------------------------------------------


def test_dispatch_calls_handlers_in_order_and_isolates_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: hook exception is logged and does not break the caller
      Given a raising plugin registered before a recording plugin
      When  on_after_create is dispatched
      Then  the recording plugin still runs and an ERROR names plugin and hook
    """

    class Raising(RecordingPlugin):
        def on_after_create(self, **kwargs: Any) -> None:
            raise RuntimeError("boom")

    registry = PluginRegistry()
    registry.register(Raising("aaa"), admin=ADMIN)
    recorder = RecordingPlugin("bbb")
    registry.register(recorder, admin=ADMIN)

    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugins"):
        registry.dispatch_hook("on_after_create", admin=ADMIN, model=int, instance=1)

    assert recorder.calls == [("on_after_create", {"admin": ADMIN, "model": int, "instance": 1})]
    (record,) = caplog.records
    assert (record.plugin, record.hook) == ("aaa", "on_after_create")  # type: ignore[attr-defined]


def test_dispatch_without_handlers_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: dispatch with no handlers is a no-op
      Given plugins that do not define on_before_delete
      Then  dispatch returns without logging and has_handlers is False
    """
    registry = _registered(RecordingPlugin())
    with caplog.at_level(logging.DEBUG, logger="hyperadmin.core.plugins"):
        registry.dispatch_hook("on_before_delete", admin=ADMIN, model=int, pk=1)
    assert caplog.records == []
    assert not registry.has_handlers("on_before_delete")
    assert registry.has_handlers("on_after_create")


def test_handler_cache_refreshes_on_new_registration() -> None:
    """
    Scenario: plugin registered after a dispatch
      Then  the next dispatch includes it
    """
    registry = PluginRegistry()
    assert not registry.has_handlers("on_after_create")
    registry.register(RecordingPlugin(), admin=ADMIN)
    assert registry.has_handlers("on_after_create")


def test_unknown_hook_name_raises() -> None:
    """
    Scenario: core fires a misspelt hook
      Then  ValueError is raised (programming error, not plugin failure)
    """
    with pytest.raises(ValueError, match="unknown plugin hook"):
        PluginRegistry().dispatch_hook("on_befor_create")


def test_async_and_non_callable_hooks_are_ignored(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: plugin defines an async hook or a non-callable attribute
      Then  the async hook is ignored with an ERROR and the attribute is skipped
    """

    class AsyncPlugin(RecordingPlugin):
        on_before_update = "not callable"

        async def on_after_update(self, **kwargs: Any) -> None:
            return None

    registry = _registered(AsyncPlugin())
    with caplog.at_level(logging.ERROR, logger="hyperadmin.core.plugins"):
        assert not registry.has_handlers("on_after_update")
    assert not registry.has_handlers("on_before_update")
    assert "async hook" in caplog.records[0].getMessage()
