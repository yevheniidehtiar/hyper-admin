"""Sidebar navigation tree: model and plugin links in domain groups.

See ``docs/specs/navigation-and-list-ux.md``. The tree is built once at mount
from plain data (registry entries, resolved plugin entries, ``nav_groups``), so
this module imports nothing from ``views/``. Permission filtering happens at
render time, because it depends on the request.
"""

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple, Union

from hyperadmin.i18n import gettext_lazy

if TYPE_CHECKING:
    import babel.support

    from hyperadmin.core.options import AdminOptions
    from hyperadmin.core.plugins import NavEntry

logger = logging.getLogger(__name__)

#: A plain label or a lazy one from ``gettext_lazy`` (rendered in the request locale).
Label = Union[str, "babel.support.LazyProxy"]

#: Icon for items that set none, so labels line up.
FALLBACK_ICON = "layout-grid"

#: Group of plugin entries that declare no ``section``.
PLUGINS_GROUP: Label = gettext_lazy("Plugins")


@dataclass(frozen=True)
class NavGroup:
    """A sidebar group, passed to ``HyperAdmin(nav_groups=[...])``.

    Models join it with ``nav_group = "Sales"`` on their admin class, and plugin
    entries with a matching ``section``. Groups that are not declared still
    appear, with these defaults.

    Attributes:
        label: Group heading; matched against ``nav_group`` and plugin sections.
        icon: Lucide icon name, shown in the collapsed rail and the palette.
        order: Groups sort by ``(order, label)``.
        collapsed: Initial state, before the user toggles the group.
    """

    label: Label
    icon: str | None = None
    order: int = 0
    collapsed: bool = False


@dataclass(frozen=True)
class NavItem:
    """One sidebar link: a model list page or a plugin page."""

    #: Pin target: the model slug (``"order"``) or ``"plugin:<url_name>"``.
    key: str
    label: Label
    #: Relative to the admin prefix, e.g. ``"/order"``.
    url: str
    icon: str
    permission: str | None
    create_url: str | None
    create_permission: str | None
    order: int
    testid: str


@dataclass(frozen=True)
class NavGroupNode:
    """A group in the built tree; the unnamed group has ``slug == ""`` and no label."""

    slug: str
    label: Label | None
    icon: str | None
    collapsed: bool
    items: tuple[NavItem, ...]


class ModelNavSource(NamedTuple):
    """A registered model as the nav tree sees it."""

    model: Any
    admin_class: Any
    options: "AdminOptions"


@dataclass(frozen=True)
class ResolvedNavEntry:
    """A plugin ``NavEntry`` whose route name resolved to an admin-relative URL."""

    entry: "NavEntry"
    url: str


def model_nav_label(model: Any, admin_class: Any) -> Label:
    """Plural sidebar label of a model, kept lazy so it renders in the request locale.

    The legacy ``name_plural`` / ``name`` attributes win over ``verbose_name_plural``.
    """
    legacy_name_plural = getattr(admin_class, "name_plural", None)
    if legacy_name_plural:
        return legacy_name_plural
    if hasattr(admin_class, "get_verbose_name_plural"):
        return admin_class.get_verbose_name_plural(model)
    return getattr(admin_class, "name", model.__name__) + "s"


def model_nav_item(source: ModelNavSource) -> NavItem:
    """The sidebar item of a registered model."""
    slug = source.model.__name__.lower()
    can_create = source.options.can_create
    return NavItem(
        key=slug,
        label=model_nav_label(source.model, source.admin_class),
        url=f"/{slug}",
        icon=getattr(source.admin_class, "icon", "") or FALLBACK_ICON,
        permission=f"view_{slug}",
        create_url=f"/{slug}/create" if can_create else None,
        create_permission=f"add_{slug}" if can_create else None,
        order=getattr(source.admin_class, "nav_order", 0),
        testid=f"nav-{slug}",
    )


def plugin_nav_item(resolved: ResolvedNavEntry) -> NavItem:
    """The sidebar item of a plugin page."""
    entry = resolved.entry
    return NavItem(
        key=f"plugin:{entry.url_name}",
        label=entry.label,
        url=resolved.url,
        icon=entry.icon or FALLBACK_ICON,
        permission=entry.permission,
        create_url=None,
        create_permission=None,
        order=entry.order,
        testid=entry.testid or f"sidebar-plugin-{entry.plugin}-{entry.url_name}",
    )


@dataclass
class _Bucket:
    key: str | None
    label: Label | None
    first_seen: int
    has_model: bool = False
    items: list[NavItem] = field(default_factory=list)


def _group_key(label: Label | None) -> str | None:
    """Labels match by their text in the default locale; empty means unnamed."""
    if label is None:
        return None
    return str(label) or None


def _model_group(admin_class: Any) -> Label | None:
    label = getattr(admin_class, "nav_group", None)
    if label is None:
        label = getattr(admin_class, "app_label", None)
    return label


def build_nav_tree(
    models: Iterable[ModelNavSource],
    plugin_entries: Iterable[ResolvedNavEntry],
    groups: Sequence[NavGroup] = (),
) -> tuple[NavGroupNode, ...]:
    """Group model and plugin items into sidebar groups.

    - A model's group is ``admin_class.nav_group``, else ``app_label``, else the
      unnamed group. A plugin entry's group is its ``section``, else "Plugins".
    - The unnamed group comes first, then the declared ``groups`` by
      ``(order, label)``, then undeclared model groups by label, then undeclared
      plugin-only groups in the order they first appear.
    - Items sort by ``(order, label)``. Groups without items are not created.
    """
    declared: dict[str, NavGroup] = {}
    for group in groups:
        declared.setdefault(str(group.label), group)

    buckets: dict[str | None, _Bucket] = {}

    def add(label: Label | None, item: NavItem, *, from_model: bool) -> None:
        key = _group_key(label)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = buckets[key] = _Bucket(key, label if key else None, len(buckets))
        bucket.has_model = bucket.has_model or from_model
        bucket.items.append(item)

    for source in models:
        add(_model_group(source.admin_class), model_nav_item(source), from_model=True)
    for resolved in plugin_entries:
        add(resolved.entry.section or PLUGINS_GROUP, plugin_nav_item(resolved), from_model=False)

    _warn_case_only_duplicates(buckets)

    def sort_key(bucket: _Bucket) -> tuple[int, int, str, int]:
        if bucket.key is None:
            return (0, 0, "", 0)
        if bucket.key in declared:
            return (1, declared[bucket.key].order, bucket.key.casefold(), 0)
        if bucket.has_model:
            return (2, 0, bucket.key.casefold(), 0)
        return (3, 0, "", bucket.first_seen)

    slugs: set[str] = set()
    nodes = []
    for bucket in sorted(buckets.values(), key=sort_key):
        config = declared.get(bucket.key) if bucket.key else None
        items = sorted(bucket.items, key=lambda item: (item.order, str(item.label).casefold()))
        nodes.append(
            NavGroupNode(
                slug=_unique_slug(bucket.key, slugs),
                label=config.label if config else bucket.label,
                icon=config.icon if config else None,
                collapsed=config.collapsed if config else False,
                items=tuple(items),
            )
        )
    return tuple(nodes)


def _warn_case_only_duplicates(buckets: dict[str | None, _Bucket]) -> None:
    """Log one warning per set of group labels that differ only in case."""
    by_fold: dict[str, list[str]] = {}
    for key in buckets:
        if key is not None:
            by_fold.setdefault(key.casefold(), []).append(key)
    for labels in by_fold.values():
        if len(labels) > 1:
            logger.warning(
                "nav groups %s differ only in case and are kept separate", sorted(labels)
            )


def _unique_slug(key: str | None, taken: set[str]) -> str:
    """URL- and test-id-safe slug of a group label; ``""`` for the unnamed group."""
    if key is None:
        return ""
    base = re.sub(r"[\W_]+", "-", key.casefold()).strip("-") or "group"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug
