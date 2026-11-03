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
permission-filtered tree.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from jinja2 import pass_context

from hyperadmin.core.navigation import filter_nav_tree, is_active_nav_url, with_legacy_items

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
    "nav_dom_id",
    "nav_is_active",
    "register_nav_globals",
    "request_nav_tree",
    "sidebar_rail",
    "visible_nav_tree",
]

#: Cookie holding the slugs of the groups the user collapsed (comma-separated, URL-encoded).
NAV_COLLAPSED_COOKIE = "ha-nav-collapsed"
#: Cookie set to ``1`` while the desktop sidebar is an icon rail.
SIDEBAR_RAIL_COOKIE = "ha-sidebar-rail"

_DOM_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


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


def nav_dom_id(key: str) -> str:
    """Template filter: ``key`` as a token safe in an element id and a CSS selector."""
    return _DOM_UNSAFE.sub("-", key)


def register_nav_globals(env: Environment) -> None:
    """Add the sidebar's template globals and the ``ha_nav_id`` filter to ``env``."""
    env.globals["visible_nav_tree"] = visible_nav_tree
    env.globals["nav_collapsed_groups"] = nav_collapsed_groups
    env.globals["sidebar_rail"] = sidebar_rail
    env.globals["nav_is_active"] = nav_is_active
    env.filters["ha_nav_id"] = nav_dom_id
