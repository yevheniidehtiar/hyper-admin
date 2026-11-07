"""Command palette data (st-v059-nav-04, ``docs/specs/navigation-and-list-ux.md``).

Pure functions over the ``nav_tree`` (``core/navigation.py``): the "New …"
actions one user may use and the JSON island the palette reads. Permission
filtering, legacy ``nav_items`` links and the active item come from
``core/navigation.py``, shared with the sidebar. The request-bound glue is
``views/palette_context.py``.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from hyperadmin.core.display import humanize_class_name
from hyperadmin.core.navigation import NavGroupNode
from hyperadmin.i18n import gettext


def palette_create_actions(
    tree: Iterable[NavGroupNode], permissions: Collection[str] | None
) -> tuple[NavGroupNode, ...]:
    """``tree`` with "New …" actions only where the user may add records.

    Run it on a tree already filtered by :func:`~hyperadmin.core.navigation.filter_nav_tree`:
    ``create_url`` is cleared where the user lacks ``create_permission``.
    ``permissions`` is ``None`` for an unrestricted user.
    """
    if permissions is None:
        return tuple(tree)
    return tuple(
        replace(
            node,
            items=tuple(
                item
                if not item.create_permission or item.create_permission in permissions
                else replace(item, create_url=None, create_permission=None)
                for item in node.items
            ),
        )
        for node in tree
    )


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
    search_url: str | None = None,
) -> dict[str, Any]:
    """The command palette's JSON data island for an already filtered ``tree``.

    Labels are rendered with ``str()``, so in the request locale. ``pins`` are
    pinned item keys in pin order; keys not in ``tree`` are dropped, so a pin
    never names a hidden model. ``current`` is the page to record as a recent
    visit (or ``None``). ``singular`` maps model keys to the name used in the
    "New …" action (the plural label otherwise). ``search_url`` is the record
    search endpoint, or ``None`` when no visible model opted in (st-v059-nav-05).
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
    return {"groups": groups, "pins": pins, "current": current, "search_url": search_url}
