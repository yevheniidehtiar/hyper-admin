"""Command palette data island (st-v059-nav-04).

Spec: ``docs/specs/navigation-and-list-ux.md`` (Palette data island, Recent items).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin, NavGroup
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.navigation import (
    ModelNavSource,
    NavGroupNode,
    ResolvedNavEntry,
    active_nav_item,
    build_nav_tree,
    filter_nav_tree,
)
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.palette import model_singular_label, palette_create_actions, palette_data
from hyperadmin.core.plugins import NavEntry
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.palette_context import ha_nav_palette


class Invoice: ...


class Bill: ...


class Order: ...


class OrderLine: ...


def _source(model: type, options: AdminOptions | None = None, **attrs: Any) -> ModelNavSource:
    admin_class = type(f"{model.__name__}Admin", (ModelAdmin,), attrs)
    admin_class.app_label = None
    return ModelNavSource(model, admin_class, options or AdminOptions())


def _tree() -> tuple[NavGroupNode, ...]:
    models = [
        _source(Invoice, nav_group="Accounting"),
        _source(Bill, nav_group="Accounting"),
        _source(Order, nav_group="Sales", verbose_name="Sales order"),
        _source(OrderLine, nav_group="Sales", options=AdminOptions(can_create=False)),
    ]
    report = ResolvedNavEntry(
        NavEntry(plugin="rpt", label="Reports", url_name="reports"), "/reports"
    )
    return build_nav_tree(models, [report], [NavGroup("Sales"), NavGroup("Accounting", order=1)])


def _keys(tree: tuple[NavGroupNode, ...]) -> list[str]:
    return [item.key for node in tree for item in node.items]


def _item(tree: tuple[NavGroupNode, ...], key: str) -> Any:
    return next(item for node in tree for item in node.items if item.key == key)


def _visible(granted: set[str] | None) -> tuple[NavGroupNode, ...]:
    """The palette's tree for a user holding ``granted`` (``None``: unrestricted)."""
    return palette_create_actions(filter_nav_tree(_tree(), granted), granted)


# -- permission filtering (shared with the sidebar) ------------------------------------


def test_forbidden_models_are_dropped_from_the_visible_tree() -> None:
    """
    Scenario: forbidden models never reach the page
      Given the user lacks view_invoice
      When  the palette tree is built for the user
      Then  it has no Invoices item, and groups without items are dropped
    """
    granted = {"view_bill", "view_order"}

    tree = _visible(granted)

    assert _keys(tree) == ["order", "bill", "plugin:reports"]
    assert [node.label for node in tree] == ["Sales", "Accounting", "Plugins"]
    only_reports = _visible(set())
    assert [node.label for node in only_reports] == ["Plugins"]
    assert _visible(None) == _tree()


def test_new_is_dropped_without_the_add_permission() -> None:
    """
    Scenario: the palette offers "New" only where allowed
      Given the user holds view_invoice but not add_invoice
      When  the palette tree is built
      Then  Invoices has no create_url, while Bills (add_bill held) keeps it
    """
    granted = {"view_invoice", "view_bill", "add_bill"}

    tree = _visible(granted)

    invoice, bill = _item(tree, "invoice"), _item(tree, "bill")
    assert (invoice.create_url, invoice.create_permission) == (None, None)
    assert bill.create_url == "/bill/create"


def test_model_singular_name_prefers_verbose_name_then_legacy_name() -> None:
    """
    Scenario: the "New …" action names one record
      Given admins with verbose_name, with the legacy name, and with neither
      When  the singular nav label is read
      Then  it is the verbose name, the legacy name, or the humanized class name
    """
    assert (
        model_singular_label(Order, type("A", (), {"verbose_name": "Sales order"})) == "Sales order"
    )
    assert model_singular_label(Order, type("B", (), {"name": "Purchase"})) == "Purchase"
    assert model_singular_label(OrderLine, type("C", (), {})) == "Order line"


# -- active_nav_item -----------------------------------------------------------------


def test_the_nav_item_of_a_page_is_a_segment_match() -> None:
    """
    Scenario: the model of a detail page is the current nav item
      When  the user is on /order/42/edit, /orderline or /
      Then  Orders, Order lines and no item match, in that order
    """
    tree = _tree()
    dashboard = ResolvedNavEntry(NavEntry(plugin="d", label="Home", url_name="home"), "/")
    with_root = build_nav_tree([], [dashboard])

    assert active_nav_item(tree, "/order/42/edit").key == "order"
    assert active_nav_item(tree, "/orderline").key == "orderline"
    assert active_nav_item(tree, "/") is None
    assert active_nav_item(with_root, "/").key == "plugin:home"
    assert active_nav_item(with_root, "/order/1") is None


# -- palette_data --------------------------------------------------------------------


def test_palette_data_carries_prefixed_urls_kinds_and_new_actions() -> None:
    """
    Scenario: the data island lists each item with its group and links
      Given the Sales, Accounting and Plugins groups
      When  the palette data is built under /admin
      Then  model items carry the admin-prefixed url, icon, group and "New …" action
      And   plugin pages are kind "page" without a create action
    """
    data = palette_data(_tree(), "/admin", singular={"order": "Sales order"})

    sales, _accounting, plugins = data["groups"]
    assert sales["label"] == "Sales"
    assert sales["items"][1] == {
        "key": "order",
        "label": "Sales orders",
        "group": "Sales",
        "url": "/admin/order",
        "icon": "layout-grid",
        "kind": "model",
        "create_url": "/admin/order/create",
        "create_label": "New Sales order",
    }
    assert "create_url" not in sales["items"][0]
    assert plugins["items"][0]["kind"] == "page"
    assert data["pins"] == []
    assert data["current"] is None


def test_pins_keep_their_order_and_never_name_a_hidden_item() -> None:
    """
    Scenario: a pin to a model the user can no longer view is hidden
      Given pins for Bills, Invoices and Orders, and a user without view_invoice
      When  the palette data is built
      Then  pins lists Bills then Orders, and those items are flagged pinned
    """
    tree = _visible({"view_bill", "view_order"})

    data = palette_data(tree, "", ["bill", "invoice", "order"])

    assert data["pins"] == ["bill", "order"]
    flagged = [i["key"] for g in data["groups"] for i in g["items"] if i.get("pinned")]
    assert sorted(flagged) == ["bill", "order"]
    assert "invoice" not in json.dumps(data)


# -- per-request glue ----------------------------------------------------------------


def _request(path: str = "/admin/", **state: Any) -> Any:
    return SimpleNamespace(state=SimpleNamespace(**state), url=SimpleNamespace(path=path))


def _ctx(request: Any = None, **values: Any) -> dict[str, Any]:
    return {"request": request, "nav_tree": _tree(), "admin_prefix": "/admin", **values}


def test_unrestricted_users_and_bridge_mode_see_everything() -> None:
    """
    Scenario: no permission set means unrestricted
      Given request.state.user_permissions is None (superuser) or unset (bridge mode)
      When  the palette data is built
      Then  every item is listed; with a permission set only the granted ones
    """

    def keys(request: Any) -> list[str]:
        data = ha_nav_palette(_ctx(request))
        return [item["key"] for group in data["groups"] for item in group["items"]]

    assert keys(_request(user_permissions=None)) == _keys(_tree())
    assert keys(_request()) == _keys(_tree())
    assert keys(_request(user_permissions=frozenset({"view_bill"}))) == ["bill", "plugin:reports"]


def test_pins_may_be_nav_items_or_keys() -> None:
    """
    Scenario: pins from the sidebar's nav_pinned_items() reach the palette
      Given pinned items (objects with a key) or plain keys
      When  the palette data is built with them
      Then  the island lists their keys in pin order
    """
    pins = [SimpleNamespace(key="bill"), "order"]

    data = ha_nav_palette(_ctx(_request()), pins)

    assert data["pins"] == ["bill", "order"]


def test_links_appended_to_nav_items_are_in_the_palette() -> None:
    """
    Scenario: a link a host appended to nav_items is searchable
      Given nav_items holds a model entry and {"name": "Profit & Loss", "url": "/reports/pl"}
      When  the palette data is built
      Then  the link is listed in the unnamed group and the model is not listed twice
    """
    extra = {"name": "Profit & Loss", "url": "/reports/pl", "icon": "receipt"}

    data = ha_nav_palette(_ctx(_request(), nav_items=[{"url": "/order"}, extra]))

    assert data["groups"][0]["label"] == ""
    assert [i["key"] for i in data["groups"][0]["items"]] == ["link:reports-pl"]
    assert data["groups"][0]["items"][0]["url"] == "/admin/reports/pl"
    assert sum(1 for g in data["groups"] for i in g["items"] if i["key"] == "order") == 1


def test_no_island_without_a_signed_in_user() -> None:
    """
    Scenario: the login page carries no navigation data
      Given auth is enabled and the request has no user
      When  the palette data is asked for
      Then  it is None (and also None outside a request)
    """
    assert ha_nav_palette(_ctx(_request("/admin/login", user=None), auth_enabled=True)) is None
    assert ha_nav_palette(_ctx()) is None


@pytest.mark.parametrize(
    ("path", "item_name", "expected"),
    [
        (
            "/admin/order/1042/edit",
            "ORD-1042",
            {"label": "ORD-1042", "group": "Sales orders", "kind": "record"},
        ),
        ("/admin/order", None, {"label": "Sales orders", "kind": "list"}),
        ("/admin/reports", None, {"label": "Reports", "kind": "page"}),
        ("/admin/order/create", None, None),
        ("/admin/", None, None),
        ("/elsewhere", None, None),
    ],
)
def test_the_page_to_record_as_recent(
    path: str, item_name: str | None, expected: dict[str, str] | None
) -> None:
    """
    Scenario: the palette lists recent records
      Given the user opened the edit page of order "ORD-1042"
      When  the page renders
      Then  the island's current entry is that record (list and plugin pages
            record their name; create forms and the dashboard record nothing)
    """
    ctx = _ctx(_request(path, user=object()), auth_enabled=True)
    if item_name is not None:
        ctx["item_name"] = item_name

    current = ha_nav_palette(ctx)["current"]

    if expected is None:
        assert current is None
    else:
        assert current == {**expected, "url": path, "icon": current["icon"]}


# -- rendering -----------------------------------------------------------------------


class CpInvoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class CpOrder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


@pytest.fixture
def admin() -> Iterator[Admin]:
    saved = dict(site._registry)
    site._registry = {}

    class CpInvoiceAdmin(ModelAdmin):
        nav_group = "Accounting"
        icon = "receipt"

    site.register(CpInvoice, CpInvoiceAdmin)
    site.register(CpOrder)
    app = FastAPI()
    instance = Admin(
        app,
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(
            create_tables=False, secret_key="x" * 40, plugins_enabled=False
        ),
    )
    instance.mount("/admin")
    yield instance
    site._registry = saved


def _render(admin: Admin, extra: dict[str, Any] | None = None, **state: Any) -> str:
    template = admin.templates.env.get_template("components/command_palette.html")
    return template.render(request=_request("/admin/cpinvoice", **state), **(extra or {}))


def test_the_palette_renders_a_permission_filtered_island(admin: Admin) -> None:
    """
    Scenario: forbidden models never reach the page
      Given the user lacks view_cpinvoice
      When  the palette component renders
      Then  the ha-nav-data island has Cp orders and no Cp invoices
      And   the dialog, the combobox input and only the used icons are rendered
    """
    html = _render(admin, user_permissions=frozenset({"view_cporder"}))

    island = re.search(r'id="ha-nav-data">(.*?)</script>', html).group(1)
    keys = [item["key"] for group in json.loads(island)["groups"] for item in group["items"]]
    assert keys == ["cporder"]
    assert "invoice" not in html.lower()
    assert 'data-testid="command-palette"' in html
    assert 'role="combobox"' in html
    assert 'id="ha-pi-clock"' in html
    assert 'id="ha-pi-receipt"' not in html


def test_an_unrestricted_user_records_the_list_page(admin: Admin) -> None:
    """
    Scenario: the palette lists recent pages
      Given an unrestricted user on /admin/cpinvoice
      When  the palette component renders
      Then  the island's current entry is the Cp invoices list, with its icon in the sprite
    """
    html = _render(admin)

    island = json.loads(re.search(r'id="ha-nav-data">(.*?)</script>', html).group(1))
    assert island["current"]["kind"] == "list"
    assert island["current"]["url"] == "/admin/cpinvoice"
    assert 'id="ha-pi-receipt"' in html
    order = next(i for g in island["groups"] for i in g["items"] if i["key"] == "cporder")
    assert order["create_label"] == "New Cp order"


def test_the_palette_reads_pins_from_nav_pinned_items_when_present(admin: Admin) -> None:
    """
    Scenario: the Pinned section is fed by the pins story's global
      Given a nav_pinned_items() global that returns the Cp orders item
      When  the palette component renders
      Then  the island pins cporder
    """
    pinned = {"nav_pinned_items": lambda: [SimpleNamespace(key="cporder")]}

    html = _render(admin, pinned)

    island = json.loads(re.search(r'id="ha-nav-data">(.*?)</script>', html).group(1))
    assert island["pins"] == ["cporder"]


def test_the_palette_lists_the_users_real_pins(admin: Admin) -> None:
    """
    Scenario: a pinned page is listed under Pinned in the palette
      Given the request carries the user's pins (request.state.nav_pins) for Cp orders
            and for a page the user may not view
      When  the palette component renders with the real nav_pinned_items() global
      Then  the island pins only cporder and flags that item pinned
      And   without loaded pins (pins off) the island pins nothing
    """
    html = _render(
        admin, nav_pins=["cpinvoice", "cporder"], user_permissions=frozenset({"view_cporder"})
    )

    island = json.loads(re.search(r'id="ha-nav-data">(.*?)</script>', html).group(1))
    assert island["pins"] == ["cporder"]
    order = next(i for g in island["groups"] for i in g["items"] if i["key"] == "cporder")
    assert order["pinned"] is True
    off = json.loads(re.search(r'id="ha-nav-data">(.*?)</script>', _render(admin)).group(1))
    assert off["pins"] == []
