"""Sidebar nav tree (``docs/specs/navigation-and-list-ux.md``, story st-v059-nav-01)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin, NavGroup, gettext_lazy
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.navigation import (
    FALLBACK_ICON,
    ModelNavSource,
    NavGroupNode,
    ResolvedNavEntry,
    build_nav_tree,
    model_nav_label,
)
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.plugins import NavEntry
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class Order: ...


class Customer: ...


class Tag: ...


class Invoice: ...


class User: ...


def _source(
    model: type, *, app_label: str | None = None, options: AdminOptions | None = None, **attrs: Any
) -> ModelNavSource:
    admin_class = type(f"{model.__name__}Admin", (ModelAdmin,), attrs)
    admin_class.app_label = app_label  # what site.register() sets
    return ModelNavSource(model, admin_class, options or AdminOptions())


def _entry(label: str, *, url: str = "/report", **fields: Any) -> ResolvedNavEntry:
    fields.setdefault("url_name", label.lower())
    return ResolvedNavEntry(NavEntry(plugin="demo", label=label, **fields), url)


def _labels(node: NavGroupNode) -> list[str]:
    return [str(item.label) for item in node.items]


def test_models_are_grouped_and_ordered() -> None:
    """
    Scenario: models are grouped and ordered
      Given OrderAdmin(nav_group="Sales", nav_order=1), CustomerAdmin(nav_group="Sales", nav_order=0)
      And   nav_groups=[NavGroup("Sales", order=0), NavGroup("Accounting", order=1)]
      When  build_nav_tree runs
      Then  the "Sales" node lists Customers then Orders, before "Accounting"
    """
    models = [
        _source(Invoice, nav_group="Accounting"),
        _source(Order, nav_group="Sales", nav_order=1),
        _source(Customer, nav_group="Sales", nav_order=0),
    ]
    groups = [NavGroup("Accounting", order=1), NavGroup("Sales", icon="receipt", order=0)]

    tree = build_nav_tree(models, (), groups)

    assert [node.label for node in tree] == ["Sales", "Accounting"]
    assert _labels(tree[0]) == ["Customers", "Orders"]
    assert tree[0].slug == "sales"
    assert tree[0].icon == "receipt"


def test_an_ungrouped_model_lands_in_the_unnamed_first_group() -> None:
    """
    Scenario: an ungrouped model lands in the unnamed first group
      Given TagAdmin with no nav_group and no app_label
      When  build_nav_tree runs
      Then  the first node has label None and contains Tags
    """
    tree = build_nav_tree([_source(Order, nav_group="Sales"), _source(Tag)], ())

    assert tree[0].label is None
    assert tree[0].slug == ""
    assert _labels(tree[0]) == ["Tags"]


def test_app_label_is_the_default_group() -> None:
    """
    Scenario: app_label is the default group
      Given site.register(Invoice, app_label="Accounting") without nav_group
      When  build_nav_tree runs
      Then  Invoices is in the "Accounting" node
    """
    tree = build_nav_tree([_source(Invoice, app_label="Accounting")], ())

    assert [(node.label, _labels(node)) for node in tree] == [("Accounting", ["Invoices"])]


def test_nav_group_wins_over_app_label() -> None:
    tree = build_nav_tree([_source(Invoice, app_label="billing", nav_group="Accounting")], ())

    assert [node.label for node in tree] == ["Accounting"]


def test_a_plugin_section_merges_into_the_same_label_group() -> None:
    """
    Scenario: a plugin section merges into the same-label group
      Given a plugin NavEntry with section "Access" and UserAdmin(nav_group="Access")
      When  build_nav_tree runs
      Then  one "Access" node holds both items
    """
    tree = build_nav_tree(
        [_source(User, nav_group="Access")],
        [_entry("Permission matrix", section="Access", icon="shield-check", order=5)],
    )

    assert len(tree) == 1
    assert _labels(tree[0]) == ["Users", "Permission matrix"]
    plugin_item = tree[0].items[1]
    assert plugin_item.key == "plugin:permission matrix"
    assert plugin_item.icon == "shield-check"
    assert plugin_item.testid == "sidebar-plugin-demo-permission matrix"
    assert plugin_item.create_url is None


def test_a_model_without_icon_gets_the_fallback_icon() -> None:
    """
    Scenario: a model without icon gets the fallback icon
      Given TagAdmin without icon
      When  build_nav_tree runs
      Then  the Tags item icon is "layout-grid"
    """
    tree = build_nav_tree([_source(Tag), _source(Order, icon="receipt")], ())

    assert {str(item.label): item.icon for item in tree[0].items} == {
        "Orders": "receipt",
        "Tags": FALLBACK_ICON,
    }
    assert FALLBACK_ICON == "layout-grid"


def test_model_item_carries_url_permissions_and_testid() -> None:
    tree = build_nav_tree(
        [_source(Order), _source(Tag, options=AdminOptions(can_create=False))], ()
    )

    order, tag = tree[0].items
    assert (order.key, order.url, order.permission, order.testid) == (
        "order",
        "/order",
        "view_order",
        "nav-order",
    )
    assert (order.create_url, order.create_permission) == ("/order/create", "add_order")
    assert (tag.create_url, tag.create_permission) == (None, None)


def test_plugin_entry_without_section_joins_the_plugins_group() -> None:
    tree = build_nav_tree([], [_entry("Report", testid="nav-report")])

    assert [str(node.label) for node in tree] == ["Plugins"]
    assert tree[0].items[0].testid == "nav-report"
    assert tree[0].items[0].icon == FALLBACK_ICON


def test_undeclared_groups_follow_the_declared_ones() -> None:
    """
    Scenario: undeclared groups sort after declared groups
      Given a declared "Sales" group, undeclared model groups "Zoo" and "Billing"
      And   plugin-only sections "Tools" then "Audit"
      When  build_nav_tree runs
      Then  the order is Sales, Billing, Zoo, Tools, Audit
    """
    tree = build_nav_tree(
        [
            _source(Order, nav_group="Zoo"),
            _source(Invoice, nav_group="Billing"),
            _source(Customer, nav_group="Sales"),
        ],
        [_entry("Shell", section="Tools"), _entry("Log", section="Audit")],
        [NavGroup("Sales", collapsed=True), NavGroup("Unused")],
    )

    assert [node.label for node in tree] == ["Sales", "Billing", "Zoo", "Tools", "Audit"]
    assert [node.collapsed for node in tree] == [True, False, False, False, False]


def test_lazy_labels_merge_with_plain_labels() -> None:
    """
    Scenario: a lazy group label merges with a plain one
      Given UserAdmin(nav_group=gettext_lazy("Access")) and a plugin section "Access"
      When  build_nav_tree runs
      Then  one group holds both, and its label stays the lazy object
    """
    lazy = gettext_lazy("Access")

    tree = build_nav_tree([_source(User, nav_group=lazy)], [_entry("Matrix", section="Access")])

    assert len(tree) == 1
    assert tree[0].label is lazy


def test_case_only_duplicate_groups_log_one_warning(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: two groups differ only in case
      Given models in "sales" and "Sales"
      When  build_nav_tree runs
      Then  they stay separate groups with distinct slugs
      And   one warning names both labels
    """
    with caplog.at_level(logging.WARNING, logger="hyperadmin.core.navigation"):
        tree = build_nav_tree(
            [_source(Order, nav_group="sales"), _source(Invoice, nav_group="Sales")], ()
        )

    assert sorted(node.slug for node in tree) == ["sales", "sales-2"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "['Sales', 'sales']" in warnings[0].getMessage()


def test_slug_of_a_label_without_word_characters() -> None:
    tree = build_nav_tree([_source(Order, nav_group="★"), _source(Tag, nav_group="Рахунки")], ())

    assert {str(node.label): node.slug for node in tree} == {"★": "group", "Рахунки": "рахунки"}


def test_empty_nav_group_is_the_unnamed_group() -> None:
    tree = build_nav_tree([_source(Order, nav_group="")], ())

    assert tree[0].label is None


def test_model_nav_label_prefers_legacy_names() -> None:
    class Plain:
        name = "Thing"

    assert model_nav_label(Order, type("A", (), {"name_plural": "All orders"})) == "All orders"
    assert model_nav_label(Order, Plain) == "Things"
    assert model_nav_label(Order, type("B", (), {})) == "Orders"


# -- wiring ---------------------------------------------------------------------------


class NvTicket(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = ""


@pytest.fixture
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


class _MatrixPlugin:
    name = "matrix"

    def on_register(self, admin: Any) -> None:
        admin.plugins.add_nav_entry(
            self, label="Dashboard", url_name="admin-dashboard", section="Support", order=1
        )


@pytest.mark.usefixtures("_clean_registry")
def test_mount_publishes_nav_tree_with_groups_and_plugins() -> None:
    """
    Scenario: the mounted admin publishes the nav tree
      Given HyperAdmin(nav_groups=[NavGroup("Support", icon="bell")]) and TicketAdmin in "Support"
      And   a plugin entry in section "Support"
      When  the admin is mounted
      Then  the nav_tree global has one "Support" group with the model then the plugin page
      And   the flat nav_items global keeps its shape
    """

    class TicketAdmin(ModelAdmin):
        nav_group = "Support"
        icon = "mail"

    site.register(NvTicket, TicketAdmin)
    app = FastAPI()
    admin = Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(
            create_tables=False, secret_key="x" * 40, plugins_enabled=False
        ),
        nav_groups=[NavGroup("Support", icon="bell")],
    )
    admin.plugins.register(_MatrixPlugin(), admin=admin)
    admin.mount("/admin")

    tree = admin.templates.env.globals["nav_tree"]
    assert [(node.label, node.icon) for node in tree] == [("Support", "bell")]
    assert [(item.key, item.url, item.icon) for item in tree[0].items] == [
        ("nvticket", "/nvticket", "mail"),
        ("plugin:admin-dashboard", "/", FALLBACK_ICON),
    ]
    assert admin.templates.env.globals["nav_items"] == [
        {
            "name": "Nv tickets",
            "url": "/nvticket",
            "icon": "mail",
            "permission": "view_nvticket",
        }
    ]
