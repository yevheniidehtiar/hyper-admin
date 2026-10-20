"""PanelDef dataclass, @panel decorator and registry helpers for detail-page panels.

See ``docs/specs/detail-panels.md``. A panel is a read-only, lazily-loaded
section of a model's detail page. Panels are declared either on
:class:`~hyperadmin.core.options.AdminOptions.panels` or as ``ModelAdmin``
methods marked with :func:`panel`; :func:`resolve_panels` merges both sources
into the final per-model list, enforcing slug uniqueness and deriving the
default permission codename.
"""

from __future__ import annotations

import dataclasses
import inspect
import re

# Runtime imports (not TYPE_CHECKING): pydantic resolves PanelDef's field annotations
# when it builds the schema for ``AdminOptions.panels``.
from collections.abc import Awaitable, Callable  # noqa: TC003
from dataclasses import dataclass
from types import MethodType
from typing import Any

from starlette.responses import Response  # noqa: TC002

_PANEL_DEF_ATTR = "_panel_def"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

#: Number of leading positional parameters a ``@panel`` method must accept:
#: ``(self, request, obj)``.
_HANDLER_POSITIONAL_ARITY = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class PanelDef:
    """Declarative definition of one detail-page panel.

    Instances are either passed to ``AdminOptions(panels=[...])`` or created by
    the :func:`panel` decorator and attached to the decorated method as
    ``method._panel_def``.

    Args:
        slug: URL-safe identifier, unique per model. Appears in the panel route
            (``/{model}/{item_id}/panels/{slug}``) and in the derived permission
            codename. Must match ``^[a-z0-9][a-z0-9_-]*$``.
        label: Human-readable tab label.
        handler: Async callable producing the panel body. Options-level
            handlers are called as ``handler(request, obj)``; ``@panel``
            methods are called as ``handler(self, request, obj)`` and are bound
            to the admin instance by :func:`resolve_panels`. ``obj`` is the
            already-loaded model instance.
        icon: Optional icon name rendered next to the tab label.
        permission: Permission codename checked before the panel renders.
            ``None`` means the default ``view_{model}_panel_{slug}`` is derived
            at registration (see :func:`panel_permission_codename`).
        enabled: Optional ``(obj) -> bool`` predicate. When it returns
            ``False`` the tab is omitted and a direct GET on the panel URL is a
            404. ``None`` means the panel is always shown.

    Raises:
        ValueError: If ``slug`` is not URL-safe.
        TypeError: If ``handler`` is not callable.
    """

    slug: str
    label: str
    handler: Callable[..., Awaitable[Response]]
    icon: str | None = None
    permission: str | None = None
    enabled: Callable[[Any], bool] | None = None

    def __post_init__(self) -> None:
        if not _SLUG_RE.match(self.slug):
            raise ValueError(f"invalid panel slug {self.slug!r}: must match {_SLUG_RE.pattern!r}")
        if not callable(self.handler):
            raise TypeError(f"panel {self.slug!r} handler must be callable")


def panel_permission_codename(model: type, slug: str) -> str:
    """Return the default permission codename for *slug* on *model*.

    Mirrors the ``view_{model}`` convention used by the detail view::

        >>> class Order: ...
        >>> panel_permission_codename(Order, "invoice")
        'view_order_panel_invoice'
    """
    return f"view_{model.__name__.lower()}_panel_{slug}"


def panel(
    label: str,
    *,
    slug: str | None = None,
    icon: str | None = None,
    permission: str | None = None,
    enabled: Callable[[Any], bool] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that marks a ``ModelAdmin`` method as a detail-page panel.

    The decorated method must be ``async`` and accept ``(self, request, obj)``
    positionally; extra keyword-only parameters are allowed. ``obj`` is the
    loaded model instance — the view fetches it once and runs the object
    permission check before any panel handler runs.

    Example::

        from hyperadmin.core.panels import panel


        class OrderAdmin(ModelAdmin):
            @panel(label="History", icon="clock")
            async def history(self, request, obj) -> Response: ...

    Args:
        label: Human-readable tab label.
        slug: URL slug; defaults to the method name.
        icon: Optional icon name for the tab.
        permission: Explicit permission codename; ``None`` derives the default.
        enabled: Optional ``(obj) -> bool`` predicate hiding the tab per instance.

    Raises:
        TypeError: If the handler is not ``async`` or does not accept three
            positional parameters ``(self, request, obj)``.
        ValueError: If the resolved slug is not URL-safe.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        _validate_handler_signature(fn)
        setattr(
            fn,
            _PANEL_DEF_ATTR,
            PanelDef(
                slug=slug if slug is not None else fn.__name__,
                label=label,
                handler=fn,
                icon=icon,
                permission=permission,
                enabled=enabled,
            ),
        )
        return fn

    return decorator


def _validate_handler_signature(fn: Callable[..., Any]) -> None:
    if not inspect.iscoroutinefunction(fn):
        raise TypeError(f"@panel handler {fn.__name__!r} must be an async function")
    positional = [
        p
        for p in inspect.signature(fn).parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) < _HANDLER_POSITIONAL_ARITY:
        raise TypeError(
            f"@panel handler {fn.__name__!r} must accept (self, request, obj); "
            f"got ({', '.join(p.name for p in positional)})"
        )


def collect_panels(cls: type) -> list[PanelDef]:
    """Return every :class:`PanelDef` declared on *cls* via :func:`panel`.

    Walks the MRO from the most basic class to *cls* so panels keep their
    definition order, and a subclass that redefines a method replaces the
    base class's panel in place.

    Args:
        cls: A ``ModelAdmin`` subclass to inspect.

    Returns:
        Panel definitions whose ``handler`` is the unbound method.
    """
    found: dict[str, PanelDef] = {}
    for klass in reversed(cls.__mro__):
        for attr_name, attr in vars(klass).items():
            panel_def = getattr(attr, _PANEL_DEF_ATTR, None)
            if isinstance(panel_def, PanelDef):
                found[attr_name] = panel_def
    return list(found.values())


def resolve_panels(admin: Any, model: type) -> list[PanelDef]:
    """Merge options-level and ``@panel`` panels for one registered model.

    The result is what the view layer iterates: ``options.panels`` first (in
    declared order), then the class-defined panels. Every returned definition
    has a concrete ``permission`` — explicit values are kept, missing ones
    become :func:`panel_permission_codename`. When *admin* is an instance,
    ``@panel`` handlers are bound to it so every handler is callable uniformly
    as ``await handler(request, obj)``.

    Args:
        admin: The ``ModelAdmin`` instance (or class) registered for *model*.
            Its ``options`` attribute, when present, supplies ``panels``.
        model: The model class, used for the default permission codename.

    Returns:
        The resolved, permission-complete panel definitions.

    Raises:
        ValueError: If two panels share a slug — ``"duplicate panel slug 'x'"``.
    """
    admin_class = admin if isinstance(admin, type) else type(admin)
    options = getattr(admin, "options", None)
    declared: list[PanelDef] = list(getattr(options, "panels", None) or [])

    class_level = collect_panels(admin_class)
    if not isinstance(admin, type):
        class_level = [
            dataclasses.replace(p, handler=MethodType(p.handler, admin)) for p in class_level
        ]

    resolved: list[PanelDef] = []
    seen: set[str] = set()
    for declared_def in [*declared, *class_level]:
        if declared_def.slug in seen:
            raise ValueError(f"duplicate panel slug {declared_def.slug!r}")
        seen.add(declared_def.slug)
        panel_def = declared_def
        if panel_def.permission is None:
            panel_def = dataclasses.replace(
                panel_def, permission=panel_permission_codename(model, panel_def.slug)
            )
        resolved.append(panel_def)
    return resolved
