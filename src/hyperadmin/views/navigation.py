"""Per-request sidebar state: the visible nav tree, collapsed groups, rail, active item.

``core/navigation.py`` builds the tree once at mount; what a request sees of it
depends on the user's permissions and on two cookies the sidebar script writes
(``docs/specs/navigation-and-list-ux.md``, "UI details"):

- ``ha-nav-collapsed``: comma-separated slugs of the groups the user collapsed.
  Once set it replaces the ``NavGroup.collapsed`` defaults; unknown slugs are ignored.
- ``ha-sidebar-rail``: ``1`` while the desktop sidebar is collapsed to an icon rail.

The cookies are read on the server, so the first paint is already right.
:func:`register_nav_globals` adds the template globals below; other templates
(the command palette, for one) reuse :func:`visible_nav_tree` for the same
permission-filtered tree and :func:`nav_pinned_items` for the user's pins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from jinja2 import pass_context

from hyperadmin.core.navigation import (
    filter_nav_tree,
    find_nav_item,
    is_active_nav_url,
    with_legacy_items,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jinja2 import Environment
    from jinja2.runtime import Context
    from starlette.requests import Request

    from hyperadmin.core.navigation import NavGroupNode, NavItem

__all__ = [
    "NAV_COLLAPSED_COOKIE",
    "SIDEBAR_RAIL_COOKIE",
    "nav_collapsed_groups",
    "nav_is_active",
    "nav_pinned_items",
    "register_nav_globals",
    "request_nav_tree",
    "sidebar_rail",
    "visible_nav_tree",
]

#: Cookie holding the slugs of the groups the user collapsed (comma-separated, URL-encoded).
NAV_COLLAPSED_COOKIE = "ha-nav-collapsed"
#: Cookie set to ``1`` while the desktop sidebar is an icon rail.
SIDEBAR_RAIL_COOKIE = "ha-sidebar-rail"


def _state(request: Any, name: str) -> Any:
    """``request.state.<name>``, or ``None`` when unset (or there is no request)."""
    state = getattr(request, "state", None)
    return getattr(state, name, None) if state is not None else None


def request_nav_tree(
    request: Any, env_globals: Mapping[str, Any] | Context
) -> tuple[NavGroupNode, ...]:
    """The nav tree ``request``'s user may see, with links hosts appended to ``nav_items``.

    Reads the ``nav_tree`` and ``nav_items`` globals from ``env_globals`` and
    ``request.state.user_permissions`` (``None`` means unrestricted). A
    ``nav_items`` entry with ``visible: False`` is hidden from signed-in users,
    as the flat sidebar did.
    """
    signed_in = _state(request, "user") is not None
    legacy = [
        entry
        for entry in env_globals.get("nav_items") or ()
        if not (signed_in and env_globals.get("auth_enabled") and entry.get("visible") is False)
    ]
    tree = with_legacy_items(tuple(env_globals.get("nav_tree") or ()), legacy)
    return filter_nav_tree(tree, _state(request, "user_permissions"))


@pass_context
def visible_nav_tree(context: Context) -> tuple[NavGroupNode, ...]:
    """Template global: the permission-filtered nav tree of the current request."""
    return request_nav_tree(context.get("request"), context)


@pass_context
def nav_collapsed_groups(context: Context) -> frozenset[str]:
    """Template global: slugs of the groups to render collapsed for this request."""
    tree = context.get("nav_tree") or ()
    request: Request | None = context.get("request")
    cookies = getattr(request, "cookies", None) or {}
    raw = cookies.get(NAV_COLLAPSED_COOKIE)
    if raw is None:
        return frozenset(group.slug for group in tree if group.collapsed and group.slug)
    known = {group.slug for group in tree if group.slug}
    return frozenset(slug for slug in unquote(raw).split(",") if slug in known)


@pass_context
def sidebar_rail(context: Context) -> bool:
    """Template global: whether the desktop sidebar renders as an icon rail."""
    request: Request | None = context.get("request")
    cookies = getattr(request, "cookies", None) or {}
    return cookies.get(SIDEBAR_RAIL_COOKIE) == "1"


@pass_context
def nav_is_active(context: Context, item: NavItem) -> bool:
    """Template global: whether ``item`` is the page being shown (or one below it)."""
    request: Request | None = context.get("request")
    if request is None:
        return False
    prefix = context.get("admin_prefix") or ""
    return is_active_nav_url(request.url.path, f"{prefix}{item.url}")


@pass_context
def nav_pinned_items(context: Context) -> list[NavItem] | None:
    """Template global: the user's visible pins, in pin order; ``None`` while pins are off.

    Pins are on for a request that carries ``request.state.nav_pins`` (the pin
    keys ``views/nav_pins.py`` loads). A pin the user may not see, or whose
    target is gone, is left out.
    """
    keys = _state(context.get("request"), "nav_pins")
    if keys is None:
        return None
    tree = visible_nav_tree(context)
    items = (find_nav_item(tree, key) for key in keys)
    return [item for item in items if item is not None]


def register_nav_globals(env: Environment) -> None:
    """Add the sidebar's template globals to ``env``."""
    env.globals["visible_nav_tree"] = visible_nav_tree
    env.globals["nav_collapsed_groups"] = nav_collapsed_groups
    env.globals["sidebar_rail"] = sidebar_rail
    env.globals["nav_is_active"] = nav_is_active
    env.globals["nav_pinned_items"] = nav_pinned_items
