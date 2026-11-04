"""Per-request data for the command palette (``docs/specs/navigation-and-list-ux.md``).

``ha_nav_palette(pins=None)`` is the palette's data island: the ``nav_tree``
filtered by ``request.state.user_permissions`` (``None`` or unset means
unrestricted), the visible pins and the current page to record as a recent
visit. It is ``None`` on pages without a signed-in user (login, MFA
challenge), so no navigation data leaks there. ``components/command_palette.html``
passes the pins from the sidebar's ``nav_pinned_items()`` global when that
global exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jinja2 import pass_context

from hyperadmin.core.palette import (
    model_singular_label,
    palette_data,
    palette_item_for_path,
    palette_tree,
)
from hyperadmin.core.registry import site

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from jinja2 import Environment
    from jinja2.runtime import Context
    from starlette.requests import Request

    from hyperadmin.core.navigation import NavGroupNode


def _has_perm(request: Request) -> Callable[[str], bool]:
    """``has_perm(codename)`` for the request's user, from ``request.state.user_permissions``."""
    permissions = getattr(request.state, "user_permissions", None)
    if permissions is None:
        return lambda _codename: True
    return permissions.__contains__


def _singular_labels() -> dict[str, Any]:
    """Model key → singular name, for the "New …" actions."""

    return {
        model.__name__.lower(): model_singular_label(model, admin_class)
        for model, admin_class in site._registry.items()
    }


@pass_context
def ha_nav_palette(ctx: Context, pins: Iterable[Any] | None = None) -> dict[str, Any] | None:
    """The palette's JSON island for this request, or ``None`` without a signed-in user.

    ``pins`` are item keys or items with a ``key`` (e.g. from ``nav_pinned_items()``).
    """
    request = ctx.get("request")
    if request is None:
        return None
    if ctx.get("auth_enabled") and getattr(request.state, "user", None) is None:
        return None
    tree = palette_tree(ctx.get("nav_tree") or (), _has_perm(request))
    prefix = ctx.get("admin_prefix") or ""
    path = request.url.path
    relative = path.removeprefix(prefix)
    keys = [getattr(pin, "key", pin) for pin in pins or ()]
    current = _recent_entry(ctx, tree, path, relative)
    return palette_data(tree, prefix, keys, current, _singular_labels())


def _recent_entry(
    ctx: Context, tree: tuple[NavGroupNode, ...], path: str, relative: str
) -> dict[str, str] | None:
    """What the palette records for this page: a list or plugin page, or a record.

    Detail and edit pages pass ``item_name``; a list page is the nav item's own
    url. Other pages (dashboard, create forms, errors) record nothing.
    """
    item = palette_item_for_path(tree, relative)
    if item is None:
        return None
    entry = {"url": path, "icon": item.icon}
    item_name = ctx.get("item_name")
    if item_name is not None and relative != item.url:
        return {**entry, "label": str(item_name), "group": str(item.label), "kind": "record"}
    if relative == item.url:
        kind = "page" if item.key.startswith("plugin:") else "list"
        return {**entry, "label": str(item.label), "kind": kind}
    return None


def register_palette_globals(env: Environment) -> None:
    """Add the ``ha_nav_palette`` global to ``env``."""
    env.globals["ha_nav_palette"] = ha_nav_palette
