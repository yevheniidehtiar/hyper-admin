"""Grouped, collapsible sidebar with an icon rail (story st-v059-nav-02).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("UI details", "Edge Cases").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from starlette.requests import Request

from hyperadmin import Admin, NavGroup
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.navigation import (
    FALLBACK_ICON,
    NavGroupNode,
    NavItem,
    filter_nav_tree,
    find_nav_item,
    is_active_nav_url,
    legacy_nav_item,
    with_legacy_items,
)
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.navigation import (
    NAV_COLLAPSED_COOKIE,
    SIDEBAR_RAIL_COOKIE,
    register_nav_globals,
    request_nav_tree,
)

HTML = {"accept": "text/html"}


class SgOrder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class SgOrderLine(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    qty: int = 0


class SgInvoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class SgTag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


class SgOrderAdmin(ModelAdmin):
    nav_group = "Sales"
    icon = "receipt"


class SgOrderLineAdmin(ModelAdmin):
    nav_group = "Sales"
    nav_order = 1


class SgInvoiceAdmin(ModelAdmin):
    nav_group = "Accounting"


@dataclass
class _User:
    id: int = 1
    username: str = "viewer"
    is_superuser: bool = False


class _Backend:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> _User:
        return self.user

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _Checker:
    def __init__(self, granted: set[str]) -> None:
        self.granted = frozenset(granted)

    async def has_permission(self, user: Any, codename: str) -> bool:
        return user.is_superuser or codename in self.granted

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.granted)


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _admin(*, granted: set[str] | None = None, collapsed: bool = False) -> tuple[Admin, TestClient]:
    """An admin with Sales (orders, order lines), Accounting (invoices) and an ungrouped Tag."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                SQLModel.metadata.create_all,
                tables=[
                    SgOrder.__table__,  # type: ignore[attr-defined]
                    SgOrderLine.__table__,  # type: ignore[attr-defined]
                    SgInvoice.__table__,  # type: ignore[attr-defined]
                    SgTag.__table__,  # type: ignore[attr-defined]
                ],
            )

    anyio.run(_setup)
    app = FastAPI()
    auth: dict[str, Any] = {}
    if granted is not None:
        auth = {"auth_backend": _Backend(_User()), "permission_checker": _Checker(granted)}
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="x" * 40),
        nav_groups=[
            NavGroup("Sales", order=0),
            NavGroup("Accounting", order=1, collapsed=collapsed),
        ],
        **auth,
    )
    site.register(SgOrder, SgOrderAdmin)
    site.register(SgOrderLine, SgOrderLineAdmin)
    site.register(SgInvoice, SgInvoiceAdmin)
    site.register(SgTag)
    admin.mount(path="/admin")
    return admin, TestClient(app)


def _client(**kwargs: Any) -> TestClient:
    return _admin(**kwargs)[1]


def _toggle(html: str, slug: str) -> str:
    """The opening tag of the toggle button of group ``slug``."""
    match = re.search(rf'<button[^>]*data-ha-nav-group="{slug}"[^>]*>', html)
    assert match, f"no toggle for group {slug!r}"
    return match.group(0)


def _link(html: str, testid: str) -> str:
    match = re.search(rf'<a [^>]*data-testid="{testid}"[^>]*>', html)
    assert match, f"no link {testid!r}"
    return match.group(0)


# -- rendered sidebar --------------------------------------------------------------


def test_groups_render_with_headings_and_icons() -> None:
    """
    Scenario: groups render with headings and icons
      Given models grouped into "Sales" and "Accounting"
      When  an admin opens the dashboard
      Then  the sidebar has headings "Sales" and "Accounting" with their items
    """
    page = _client().get("/admin/", headers=HTML).text

    sales = page.index('data-testid="nav-group-sales"')
    accounting = page.index('data-testid="nav-group-accounting"')
    assert sales < accounting
    assert '<span class="ha-nav-group__label">Sales</span>' in page
    assert '<span class="ha-nav-group__label">Accounting</span>' in page
    assert sales < page.index('data-testid="nav-sgorder"') < accounting
    assert page.index('data-testid="nav-sginvoice"') > accounting
    # Lucide icon for the model that sets one; the fallback for the others.
    assert "ha-icon" in page.split('data-testid="nav-sgorder"')[1].split("</a>")[0]


def test_the_unnamed_group_has_no_heading() -> None:
    """
    Scenario: an ungrouped model is listed without a heading
      Given SgTag has no nav_group and no app_label
      When  an admin opens the dashboard
      Then  its link renders before the first group heading, in a group without a test id
    """
    page = _client().get("/admin/", headers=HTML).text

    assert page.index('data-testid="nav-sgtag"') < page.index('data-testid="nav-group-sales"')
    assert 'id="ha-nav-top"' in page
    assert 'data-testid="nav-group-"' not in page


def test_a_collapsed_group_stays_collapsed_after_reload() -> None:
    """
    Scenario: a collapsed group stays collapsed after reload
      Given the "Accounting" group is expanded
      When  the user collapses it and reloads
      Then  the "Accounting" toggle has aria-expanded="false" in the server HTML
    """
    client = _client()
    assert 'aria-expanded="true"' in _toggle(client.get("/admin/", headers=HTML).text, "accounting")

    client.cookies.set(NAV_COLLAPSED_COOKIE, "accounting%2Cnot-a-group")
    page = client.get("/admin/", headers=HTML).text

    assert 'aria-expanded="false"' in _toggle(page, "accounting")
    assert 'aria-expanded="true"' in _toggle(page, "sales")
    assert "ha-nav-group ha-nav-group--collapsed" in page


def test_nav_group_collapsed_is_the_default_until_the_user_toggles() -> None:
    """
    Scenario: NavGroup(collapsed=True) applies until the cookie exists
      Given NavGroup("Accounting", collapsed=True)
      When  a first visit renders, and then a visit with an empty ha-nav-collapsed cookie
      Then  Accounting starts collapsed, and is expanded once the user expanded it
    """
    client = _client(collapsed=True)
    assert 'aria-expanded="false"' in _toggle(
        client.get("/admin/", headers=HTML).text, "accounting"
    )

    client.cookies.set(NAV_COLLAPSED_COOKIE, "")
    assert 'aria-expanded="true"' in _toggle(client.get("/admin/", headers=HTML).text, "accounting")


def test_the_rail_state_comes_from_its_cookie() -> None:
    """
    Scenario: the rail hides labels but keeps accessible names
      When  the user activates the rail toggle (cookie ha-sidebar-rail=1) and reloads
      Then  the shell renders data-collapsed="true", the toggle is pressed
      And   every nav link keeps its text label and a title tooltip
    """
    client = _client()
    page = client.get("/admin/", headers=HTML).text
    assert 'class="ha-layout" data-collapsed="false"' in page

    client.cookies.set(SIDEBAR_RAIL_COOKIE, "1")
    page = client.get("/admin/", headers=HTML).text

    assert 'class="ha-layout" data-collapsed="true"' in page
    assert re.search(r'data-testid="sidebar-rail-toggle"[^>]*aria-pressed="true"', page)
    assert 'title="Sg orders"' in _link(page, "nav-sgorder")
    assert '<span class="ha-nav-item__label">Sg orders</span>' in page


def test_the_model_of_an_edit_page_is_active() -> None:
    """
    Scenario: the model of an edit page is active
      When  the user opens /admin/sgorder/42/edit
      Then  the Orders link has aria-current="page" and Order lines does not
    """
    page = _client().get("/admin/sgorder/42/edit", headers=HTML).text

    assert 'aria-current="page"' in _link(page, "nav-sgorder")
    assert 'aria-current="page"' not in _link(page, "nav-sgorderline")


def test_permission_filtering_removes_empty_groups() -> None:
    """
    Scenario: permission filtering removes empty groups
      Given the user may view none of the "Accounting" models
      When  the user opens the dashboard
      Then  no "Accounting" heading is rendered
    """
    page = _client(granted={"view_sgorder"}).get("/admin/", headers=HTML).text

    assert 'data-testid="nav-group-sales"' in page
    assert 'data-testid="nav-sgorder"' in page
    assert 'data-testid="nav-sgorderline"' not in page
    assert 'data-testid="nav-group-accounting"' not in page
    assert "Accounting" not in page


def test_links_appended_to_nav_items_after_mount_still_render() -> None:
    """
    Scenario: a link a host appended to nav_items stays in the sidebar
      Given a host appends {"name": "Profit & Loss Report", "url": "/reports/profit-loss"}
            to the nav_items global after admin.mount()
      When  an admin opens the dashboard
      Then  the link renders in the unnamed top group, after its own items, with the fallback icon
    """
    admin, client = _admin()
    admin.templates.env.globals["nav_items"].append(
        {"name": "Profit & Loss Report", "url": "/reports/profit-loss"}
    )

    page = client.get("/admin/", headers=HTML).text

    link = _link(page, "nav-reports-profit-loss")
    assert 'href="/admin/reports/profit-loss"' in link
    top = page.split('id="ha-nav-top"')[1].split("</ul>")[0]
    assert top.index('data-testid="nav-sgtag"') < top.index('data-testid="nav-reports-profit-loss"')


# -- pure helpers ------------------------------------------------------------------


def _item(key: str, *, url: str | None = None, permission: str | None = None) -> NavItem:
    return NavItem(
        key=key,
        label=key.title(),
        url=url or f"/{key}",
        icon=FALLBACK_ICON,
        permission=permission,
        create_url=None,
        create_permission=None,
        order=0,
        testid=f"nav-{key}",
    )


def _group(slug: str, *items: NavItem) -> NavGroupNode:
    return NavGroupNode(slug, slug.title() if slug else None, None, collapsed=False, items=items)


def test_legacy_nav_item_derives_key_and_testid_from_the_url() -> None:
    """
    Scenario: a nav_items dict becomes a nav item
      Given {"name": "P&L", "url": "/reports/profit-loss", "icon": "receipt", "permission": "view_pl"}
      When  legacy_nav_item converts it
      Then  the key is link:reports-profit-loss, the test id nav-reports-profit-loss
      And   the icon and permission are kept; without an icon the fallback is used
    """
    item = legacy_nav_item(
        {"name": "P&L", "url": "/reports/profit-loss", "icon": "receipt", "permission": "view_pl"}
    )

    assert (item.key, item.testid, item.icon, item.permission) == (
        "link:reports-profit-loss",
        "nav-reports-profit-loss",
        "receipt",
        "view_pl",
    )
    bare = legacy_nav_item({"url": "/"})
    assert (bare.key, bare.label, bare.icon, bare.permission) == (
        "link:link",
        "/",
        FALLBACK_ICON,
        None,
    )


def test_with_legacy_items_adds_only_unknown_urls() -> None:
    """
    Scenario: nav_items entries already in the tree are not duplicated
      Given a tree with /order and nav_items for /order and /reports
      When  with_legacy_items merges them
      Then  only /reports is added, to the unnamed group created at the top
    """
    tree = (_group("sales", _item("order")),)

    merged = with_legacy_items(tree, [{"name": "Orders", "url": "/order"}, {"url": "/reports"}])

    assert [g.slug for g in merged] == ["", "sales"]
    assert [i.url for i in merged[0].items] == ["/reports"]
    assert with_legacy_items(tree, [{"url": "/order"}]) == tree


def test_with_legacy_items_appends_to_an_existing_unnamed_group() -> None:
    tree = (_group("", _item("tag")), _group("sales", _item("order")))

    merged = with_legacy_items(tree, [{"url": "/reports"}])

    assert [i.url for i in merged[0].items] == ["/tag", "/reports"]
    assert merged[1] is tree[1]


def test_filter_nav_tree_drops_items_and_empty_groups() -> None:
    """
    Scenario: a group without visible items is dropped
      Given Sales with order (view_order) and a link without permission, Accounting with invoice
      When  the tree is filtered for a user holding only view_order
      Then  Sales keeps both items and Accounting is gone; None means unrestricted
    """
    sales = _group("sales", _item("order", permission="view_order"), _item("help"))
    accounting = _group("accounting", _item("invoice", permission="view_invoice"))
    partial = _group("mixed", _item("order", permission="view_order"), _item("x", permission="no"))

    assert filter_nav_tree((sales, accounting), {"view_order"}) == (sales,)
    assert filter_nav_tree((sales, accounting), None) == (sales, accounting)
    assert [i.key for i in filter_nav_tree((partial,), {"view_order"})[0].items] == ["order"]


def test_find_nav_item_by_key() -> None:
    tree = (_group("sales", _item("order")),)

    assert find_nav_item(tree, "order") is tree[0].items[0]
    assert find_nav_item(tree, "nope") is None


@pytest.mark.parametrize(
    ("path", "url", "active"),
    [
        ("/admin/order", "/admin/order", True),
        ("/admin/order/42/edit", "/admin/order", True),
        ("/admin/orderline", "/admin/order", False),
        ("/admin/order", "/admin/order/", True),
        ("/", "", True),
        ("/admin", "", False),
    ],
)
def test_active_matching_uses_whole_segments(path: str, url: str, active: bool) -> None:
    """
    Scenario: active matching is by URL segment prefix
      Given an item url
      When  a path is compared with it
      Then  the path itself and paths below it match, a longer sibling name does not
    """
    assert is_active_nav_url(path, url) is active


def _request(cookies: str = "", **state: Any) -> Request:
    headers = [(b"cookie", cookies.encode())] if cookies else []
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": headers})
    for key, value in state.items():
        setattr(request.state, key, value)
    return request


def _render(source: str, **context: Any) -> str:
    env = Environment(autoescape=True)
    register_nav_globals(env)
    return env.from_string(source).render(**context)


def test_collapsed_groups_ignore_unknown_slugs_and_fall_back_to_defaults() -> None:
    """
    Scenario: the ha-nav-collapsed cookie holds unknown slugs
      Given groups sales and accounting (accounting collapsed by default)
      When  the cookie names sales and a removed group, or is absent
      Then  only sales is collapsed; without the cookie the NavGroup default applies
    """
    tree = (
        _group("", _item("tag")),
        _group("sales", _item("order")),
        NavGroupNode("accounting", "Accounting", None, collapsed=True, items=(_item("invoice"),)),
    )
    source = "{{ nav_collapsed_groups() | sort | join(',') }}"

    with_cookie = _request(f"{NAV_COLLAPSED_COOKIE}=sales%2Cgone%2C")
    assert _render(source, request=with_cookie, nav_tree=tree) == "sales"
    assert _render(source, request=_request(), nav_tree=tree) == "accounting"
    assert _render(source, nav_tree=tree) == "accounting"


def test_sidebar_rail_and_active_globals_without_a_request() -> None:
    assert _render("{{ sidebar_rail() }}") == "False"
    assert _render("{{ sidebar_rail() }}", request=_request(f"{SIDEBAR_RAIL_COOKIE}=0")) == "False"
    assert _render("{{ nav_is_active(item) }}", item=_item("order")) == "False"


def test_request_nav_tree_hides_invisible_legacy_items_from_signed_in_users() -> None:
    """
    Scenario: a nav_items entry with visible=False is hidden from signed-in users
      Given auth is enabled and nav_items holds one visible and one visible=False link
      When  a signed-in user's tree is built, and an anonymous one's
      Then  the signed-in user sees only the visible link; the anonymous request sees both
    """
    env_globals = {
        "nav_tree": (),
        "auth_enabled": True,
        "nav_items": [{"url": "/a"}, {"url": "/b", "visible": False}],
    }

    signed_in = request_nav_tree(_request(user=_User(), user_permissions=None), env_globals)
    anonymous = request_nav_tree(_request(), env_globals)

    assert [i.url for i in signed_in[0].items] == ["/a"]
    assert [i.url for i in anonymous[0].items] == ["/a", "/b"]
    assert request_nav_tree(None, {}) == ()
