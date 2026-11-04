"""Command palette data (st-v059-nav-04, ``docs/specs/navigation-and-list-ux.md``).

Pure functions over the ``nav_tree`` (``core/navigation.py``): which items one
user may open, which item a page is on, and the JSON island the palette reads.
The request-bound glue is ``views/palette_context.py``.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from hyperadmin.core.display import humanize_class_name
from hyperadmin.core.navigation import NavGroupNode, NavItem
from hyperadmin.i18n import gettext


def palette_tree(
    tree: Iterable[NavGroupNode], has_perm: Callable[[str], bool]
) -> tuple[NavGroupNode, ...]:
    """The part of ``tree`` one user may open.

    Items whose ``permission`` the user lacks are dropped, and so are groups left
    without items. ``create_url`` is cleared where the user lacks
    ``create_permission``, so no "New …" action is offered there.
    """
    nodes = []
    for node in tree:
        items = tuple(
            item
            if not item.create_permission or has_perm(item.create_permission)
            else replace(item, create_url=None, create_permission=None)
            for item in node.items
            if not item.permission or has_perm(item.permission)
        )
        if items:
            nodes.append(replace(node, items=items))
    return tuple(nodes)


def palette_item_for_path(tree: Iterable[NavGroupNode], path: str) -> NavItem | None:
    """The item whose page ``path`` (admin-relative) is on: its url, or a page below it.

    A segment match, so ``/order`` matches ``/order/42/edit`` but not
    ``/orderline``; the root url ``/`` (a dashboard entry) matches only itself.
    The longest url wins.
    """
    best: NavItem | None = None
    for node in tree:
        for item in node.items:
            base = item.url.rstrip("/")
            on_item = path == item.url or (bool(base) and path.startswith(base + "/"))
            if on_item and (best is None or len(item.url) > len(best.url)):
                best = item
    return best


def model_singular_label(model: Any, admin_class: Any) -> Any:
    """Singular model name: ``verbose_name``, the legacy ``name``, else the humanized class name."""
    return (
        getattr(admin_class, "verbose_name", None)
        or getattr(admin_class, "name", None)
        or humanize_class_name(model.__name__)
    )


def palette_data(
    tree: Sequence[NavGroupNode],
    prefix: str = "",
    pins: Sequence[str] = (),
    current: dict[str, str] | None = None,
    singular: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The command palette's JSON data island for an already filtered ``tree``.

    Labels are rendered with ``str()``, so in the request locale. ``pins`` are
    pinned item keys in pin order; keys not in ``tree`` are dropped, so a pin
    never names a hidden model. ``current`` is the page to record as a recent
    visit (or ``None``). ``singular`` maps model keys to the name used in the
    "New …" action (the plural label otherwise).
    """
    visible = {item.key for node in tree for item in node.items}
    pins = [key for key in pins if key in visible]
    names = singular or {}
    groups = []
    for node in tree:
        group = str(node.label or "")
        items = []
        for item in node.items:
            entry: dict[str, Any] = {
                "key": item.key,
                "label": str(item.label),
                "group": group,
                "url": prefix + item.url,
                "icon": item.icon,
                "kind": "page" if item.key.startswith("plugin:") else "model",
            }
            if item.create_url:
                name = names.get(item.key, item.label)
                entry["create_url"] = prefix + item.create_url
                entry["create_label"] = gettext("New %(name)s") % {"name": str(name)}
            if item.key in pins:
                entry["pinned"] = True
            items.append(entry)
        groups.append({"label": group, "items": items})
    return {"groups": groups, "pins": pins, "current": current}
