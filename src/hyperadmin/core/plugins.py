"""Plugin contract, registry and UI-extension seams (SDD ``docs/specs/plugin-registry.md``).

Plugins are discovered through the ``hyperadmin.plugins`` entry-point group. Each
plugin's ``on_register(admin)`` contributes UI seams (pages, nav entries, template
dirs, a static dir, permission codenames) through the registry's ``add_*`` methods;
the registry only *collects* them. Mounting, Jinja wiring, sidebar rendering and
permission sync happen in ``Admin.mount()`` via ``plugin_wiring``, so this module stays a leaf:
no HTTP, no ORM, no imports from ``views/``, ``adapters/`` or ``auth/``.
"""

from __future__ import annotations

import inspect
import logging
import os
import re
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from pydantic import BaseModel

logger = logging.getLogger(__name__)

#: Entry-point group plugins declare in their ``pyproject.toml``.
PLUGIN_ENTRY_POINT_GROUP = "hyperadmin.plugins"
#: Comma-separated plugin names to skip; unioned with ``disabled=``.
DISABLED_PLUGINS_ENV = "HYPERADMIN_DISABLED_PLUGINS"

#: Lifecycle hooks ``dispatch_hook`` accepts (SDD "Hook signatures").
LIFECYCLE_HOOKS: frozenset[str] = frozenset(
    {
        "on_model_register",
        "on_before_create",
        "on_after_create",
        "on_before_update",
        "on_after_update",
        "on_before_delete",
        "on_after_delete",
        "on_before_adapter_call",
        "on_after_adapter_call",
    }
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_CODENAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PREFIX_RE = re.compile(r"^(/[a-z0-9][a-z0-9_-]*)+$")

SkipReason = Literal["disabled", "duplicate", "load_error", "invalid", "register_error"]


class PluginError(Exception):
    """A plugin misused the registration API (bad argument, wrong time, conflict)."""


@runtime_checkable
class Plugin(Protocol):
    """What every plugin provides. All lifecycle hooks are optional methods.

    A plugin may also define ``settings_model`` (a pydantic model class); the
    registry validates the operator's settings into it before ``on_register``.
    """

    name: str

    def on_register(self, admin: Any) -> None: ...


@dataclass(frozen=True)
class PluginPage:
    """A router mounted inside the admin sub-app under ``prefix``."""

    plugin: str
    router: Any
    prefix: str


@dataclass(frozen=True)
class NavEntry:
    """A sidebar link to a named route in the ``hyperadmin:`` namespace."""

    plugin: str
    label: str
    url_name: str
    icon: str | None = None
    permission: str | None = None
    section: str | None = None
    order: int = 0
    url_params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginTemplateDir:
    """A template search path appended after the core templates."""

    plugin: str
    path: Path


@dataclass(frozen=True)
class PluginStaticDir:
    """A static directory served under ``{prefix}/static/plugins/<plugin>/``."""

    plugin: str
    path: Path

    @property
    def mount_path(self) -> str:
        """Mount path relative to the admin sub-app."""
        return f"/static/plugins/{self.plugin}"


@dataclass(frozen=True)
class PluginPermission:
    """A permission codename a plugin declares (e.g. ``view_report_sales``)."""

    plugin: str
    codename: str
    name: str


@dataclass
class _Contributions:
    pages: list[PluginPage] = field(default_factory=list)
    nav_entries: list[NavEntry] = field(default_factory=list)
    template_dirs: list[PluginTemplateDir] = field(default_factory=list)
    static_dir: PluginStaticDir | None = None
    permissions: list[PluginPermission] = field(default_factory=list)


def parse_disabled_env(value: str | None) -> set[str]:
    """Parse ``HYPERADMIN_DISABLED_PLUGINS``: comma-separated, blanks ignored."""
    if not value:
        return set()
    return {token.strip() for token in value.split(",") if token.strip()}


class PluginRegistry:
    """Discovered plugins, their settings, collected UI seams and hook dispatch."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._origins: dict[str, str] = {}
        self._settings: dict[str, Any] = {}
        self._contributions: dict[str, _Contributions] = {}
        self._skipped: dict[str, SkipReason] = {}
        self._handlers: dict[str, list[tuple[str, Callable[..., Any]]]] = {}
        self._registering: str | None = None

    # -- discovery & registration -------------------------------------------------

    @classmethod
    def discover(
        cls,
        *,
        admin: Any,
        disabled: Iterable[str] = (),
        settings: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> PluginRegistry:
        """Load every ``hyperadmin.plugins`` entry point, isolating failures.

        Entry points are processed sorted by ``(name, value)`` so the order is
        deterministic; a later entry point reusing a name is skipped.
        """
        registry = cls()
        registry.load_entry_points(admin=admin, disabled=disabled, settings=settings)
        return registry

    def load_entry_points(
        self,
        *,
        admin: Any,
        disabled: Iterable[str] = (),
        settings: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Like :meth:`discover`, into this registry.

        ``Admin`` assigns ``admin.plugins`` first and then loads into it, so a
        plugin's ``on_register`` can call ``admin.plugins.add_*``.
        """
        skip = set(disabled) | parse_disabled_env(os.environ.get(DISABLED_PLUGINS_ENV))
        settings = settings or {}
        eps = sorted(
            entry_points(group=PLUGIN_ENTRY_POINT_GROUP), key=lambda ep: (ep.name, ep.value)
        )
        seen: dict[str, str] = {}
        for ep in eps:
            if ep.name in seen:
                logger.warning(
                    "plugin %r from %s skipped: name already taken by %s",
                    ep.name,
                    ep.value,
                    seen[ep.name],
                    extra={"plugin": ep.name, "plugin_entry_point": ep.value},
                )
                continue
            seen[ep.name] = ep.value
            if ep.name in skip:
                self._skipped[ep.name] = "disabled"
                continue
            plugin = self._load(ep)
            if plugin is None:
                continue
            self.register(plugin, admin=admin, settings=settings.get(ep.name), origin=ep.value)

    def _load(self, ep: EntryPoint) -> Plugin | None:
        try:
            obj = ep.load()
            plugin = obj() if inspect.isclass(obj) else obj
        except Exception:
            logger.exception(
                "plugin %r failed to load",
                ep.name,
                extra={"plugin": ep.name, "plugin_entry_point": ep.value},
            )
            self._skipped[ep.name] = "load_error"
            return None
        if not isinstance(plugin, Plugin) or plugin.name != ep.name:
            logger.error(
                "plugin %r skipped: %s is not a Plugin whose name matches the entry point",
                ep.name,
                ep.value,
                extra={"plugin": ep.name, "plugin_entry_point": ep.value},
            )
            self._skipped[ep.name] = "invalid"
            return None
        return plugin

    def register(
        self,
        plugin: Plugin,
        *,
        admin: Any,
        settings: Mapping[str, Any] | None = None,
        origin: str | None = None,
    ) -> bool:
        """Validate settings, run ``on_register`` and keep the plugin on success.

        Any failure is logged and rolls back everything the plugin contributed;
        returns whether the plugin was registered.
        """
        name = plugin.name
        if not isinstance(name, str) or not _NAME_RE.match(name) or name in self._plugins:
            logger.error(
                "plugin %r skipped: invalid or duplicate name", name, extra={"plugin": name}
            )
            return False
        self._origins[name] = origin or f"{type(plugin).__module__}:{type(plugin).__qualname__}"
        self._contributions[name] = _Contributions()
        self._registering = name
        try:
            settings_model: type[BaseModel] | None = getattr(plugin, "settings_model", None)
            if settings_model is not None:
                self._settings[name] = settings_model(**(settings or {}))
            plugin.on_register(admin)
        except Exception:
            logger.exception(
                "plugin %r failed to register", name, extra={"plugin": name, "hook": "on_register"}
            )
            self._contributions.pop(name)
            self._settings.pop(name, None)
            self._skipped[name] = "register_error"
            return False
        finally:
            self._registering = None
        self._plugins[name] = plugin
        self._handlers.clear()
        return True

    # -- mapping-like access ------------------------------------------------------

    def __contains__(self, name: object) -> bool:
        return name in self._plugins

    def __getitem__(self, name: str) -> Plugin:
        return self._plugins[name]

    def __bool__(self) -> bool:
        return bool(self._plugins)

    def __len__(self) -> int:
        return len(self._plugins)

    def names(self) -> list[str]:
        """Registered plugin names, in registration order."""
        return list(self._plugins)

    def origin(self, name: str) -> str:
        """Import path (entry-point value) a plugin was loaded from."""
        return self._origins[name]

    @property
    def skipped(self) -> dict[str, SkipReason]:
        """Plugins that were found but not registered, with the reason."""
        return dict(self._skipped)

    def settings(self, name: str) -> Any:
        """The validated ``settings_model`` instance of a plugin, or ``None``."""
        return self._settings.get(name)

    # -- UI seams (callable only from the plugin's own on_register) ---------------

    def _contributing(self, plugin: Plugin) -> _Contributions:
        if self._registering is None or plugin.name != self._registering:
            raise PluginError(
                f"plugin {plugin.name!r} may only register UI seams from its own on_register()"
            )
        return self._contributions[plugin.name]

    def _all(self) -> Iterable[_Contributions]:
        return (self._contributions[name] for name in self._plugins)

    def add_page(self, plugin: Plugin, router: Any, *, prefix: str | None = None) -> PluginPage:
        """Mount ``router`` (a FastAPI ``APIRouter``) under ``prefix`` in the admin.

        ``prefix`` defaults to ``/<plugin name>`` and must be unique across plugins.
        """
        contrib = self._contributing(plugin)
        prefix = prefix if prefix is not None else f"/{plugin.name}"
        if not _PREFIX_RE.match(prefix):
            raise PluginError(f"invalid page prefix {prefix!r}")
        if not hasattr(router, "routes"):
            raise PluginError(f"{router!r} is not a router")
        taken = {p.prefix for c in (*self._all(), contrib) for p in c.pages}
        if prefix in taken:
            raise PluginError(f"page prefix {prefix!r} is already used by another plugin")
        page = PluginPage(plugin=plugin.name, router=router, prefix=prefix)
        contrib.pages.append(page)
        return page

    def add_nav_entry(  # noqa: PLR0913 - one keyword per NavEntry field
        self,
        plugin: Plugin,
        *,
        label: str,
        url_name: str,
        icon: str | None = None,
        permission: str | None = None,
        section: str | None = None,
        order: int = 0,
        url_params: Mapping[str, Any] | None = None,
    ) -> NavEntry:
        """Add a sidebar link; ``url_name`` is resolved in the ``hyperadmin:`` namespace."""
        contrib = self._contributing(plugin)
        if not label or not url_name:
            raise PluginError("nav entry needs a label and a url_name")
        entry = NavEntry(
            plugin=plugin.name,
            label=label,
            url_name=url_name,
            icon=icon,
            permission=permission,
            section=section,
            order=order,
            url_params=dict(url_params or {}),
        )
        contrib.nav_entries.append(entry)
        return entry

    def add_template_dir(self, plugin: Plugin, path: str | os.PathLike[str]) -> PluginTemplateDir:
        """Add a template search path (searched after core and host templates)."""
        contrib = self._contributing(plugin)
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            raise PluginError(f"template dir {resolved} does not exist")
        template_dir = PluginTemplateDir(plugin=plugin.name, path=resolved)
        contrib.template_dirs.append(template_dir)
        return template_dir

    def set_static_dir(self, plugin: Plugin, path: str | os.PathLike[str]) -> PluginStaticDir:
        """Serve ``path`` under ``{prefix}/static/plugins/<plugin name>/`` (one per plugin)."""
        contrib = self._contributing(plugin)
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            raise PluginError(f"static dir {resolved} does not exist")
        if contrib.static_dir is not None:
            raise PluginError(f"plugin {plugin.name!r} already has a static dir")
        contrib.static_dir = PluginStaticDir(plugin=plugin.name, path=resolved)
        return contrib.static_dir

    def add_permission(
        self, plugin: Plugin, codename: str, name: str | None = None
    ) -> PluginPermission:
        """Declare a permission codename so it shows in the permission system."""
        contrib = self._contributing(plugin)
        if not _CODENAME_RE.match(codename):
            raise PluginError(f"invalid permission codename {codename!r}")
        taken = {p.codename for c in (*self._all(), contrib) for p in c.permissions}
        if codename in taken:
            raise PluginError(f"permission {codename!r} is already declared")
        perm = PluginPermission(
            plugin=plugin.name,
            codename=codename,
            name=name or f"Can {codename.replace('_', ' ')}",
        )
        contrib.permissions.append(perm)
        return perm

    # -- collected seams (consumed by Admin wiring) -------------------------------

    @property
    def pages(self) -> list[PluginPage]:
        return [p for c in self._all() for p in c.pages]

    @property
    def nav_entries(self) -> list[NavEntry]:
        """Nav entries sorted by ``(order, label)``; ties keep plugin order."""
        entries = [e for c in self._all() for e in c.nav_entries]
        return sorted(entries, key=lambda e: (e.order, e.label))

    @property
    def template_dirs(self) -> list[PluginTemplateDir]:
        return [d for c in self._all() for d in c.template_dirs]

    @property
    def static_dirs(self) -> list[PluginStaticDir]:
        return [c.static_dir for c in self._all() if c.static_dir is not None]

    @property
    def permissions(self) -> list[PluginPermission]:
        return [p for c in self._all() for p in c.permissions]

    # -- lifecycle hooks ----------------------------------------------------------

    def _handlers_for(self, hook: str) -> list[tuple[str, Callable[..., Any]]]:
        if hook not in LIFECYCLE_HOOKS:
            raise ValueError(f"unknown plugin hook {hook!r}")
        handlers = self._handlers.get(hook)
        if handlers is None:
            handlers = []
            for name, plugin in self._plugins.items():
                handler = getattr(plugin, hook, None)
                if not callable(handler):
                    continue
                if inspect.iscoroutinefunction(handler):
                    logger.error(
                        "plugin %r: async hook %s is not supported; ignored",
                        name,
                        hook,
                        extra={"plugin": name, "hook": hook},
                    )
                    continue
                handlers.append((name, handler))
            self._handlers[hook] = handlers
        return handlers

    def has_handlers(self, hook: str) -> bool:
        """Whether any plugin implements ``hook`` (hot-path short-circuit)."""
        return bool(self._handlers_for(hook))

    def dispatch_hook(self, hook: str, /, **kwargs: Any) -> None:
        """Call every plugin's ``hook`` in plugin order; exceptions are logged, not raised."""
        for name, handler in self._handlers_for(hook):
            try:
                handler(**kwargs)
            except Exception:  # noqa: PERF203 - per-plugin isolation is the contract
                logger.exception(
                    "plugin %r hook %s raised", name, hook, extra={"plugin": name, "hook": hook}
                )
