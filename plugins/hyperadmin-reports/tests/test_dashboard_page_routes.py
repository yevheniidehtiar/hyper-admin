"""Integration tests for the dashboard routes and the home page claim (#462).

The first eleven tests map 1:1 to the scenarios of
``.meta/epics/epicdashboard-dashboard-builder-with-widgets/stories/featviews-create-dashboard-view-handler.md``.
A real admin is mounted with the ``reports`` plugin discovered from its entry point.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
from dashboard_support import (
    HX,
    Mounted,
    OrderRevenueReport,
    PayrollTotalReport,
    TextWidget,
    clean_registry,
    make_engine,
    mount,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from hyperadmin_reports import LayoutStore, StatWidget, register_widget
from hyperadmin_reports.dashboard.layout import LAYOUT_TABLE_NAME
from hyperadmin_reports.plugin import STATIC_DIR

WELCOME = "Welcome to HyperAdmin Dashboard"
GRID = 'data-testid="dashboard-grid"'
ALICE = {"x-user": "alice"}
#: SHA-256 of ``Sortable.min.js`` in the sortablejs 1.15.6 npm release.
SORTABLE_SHA256 = "6d0a831fc19b4bae851797ad3393157e861afb7862459c11226359b27e2c4337"
SORTABLE_PATH = "/admin/static/plugins/reports/vendor/sortable-1.15.6.min.js"


@pytest.fixture(autouse=True)
def _registered() -> Iterator[None]:
    yield from clean_registry()


def _abc() -> None:
    for key in ("a", "b", "c"):
        register_widget(TextWidget(key, permission=f"view_{key}"))


def _dashboard(
    tmp_path: Path, *, layouts: bool = True, **kwargs: Any
) -> tuple[Mounted, AsyncEngine]:
    """Widgets A, B, C and a payroll stat, mounted (alice is the default user)."""
    _abc()
    register_widget(StatWidget(PayrollTotalReport))
    engine = make_engine(tmp_path, layouts=layouts)
    return mount(engine, **kwargs), engine


def _order(html: str) -> list[str]:
    return re.findall(r'data-widget-key="([^"]+)"', html)


def _page_order(mounted: Mounted, user: str = "alice", path: str = "/admin/") -> list[str]:
    response = mounted.client.get(path, headers={"x-user": user})
    assert response.status_code == 200
    return _order(response.text)


def _saved(engine: AsyncEngine, user_key: int) -> list[str] | None:
    return anyio.run(LayoutStore(engine).load, user_key)


def test_dashboard_replaces_the_welcome_page_when_widgets_are_registered(tmp_path: Path) -> None:
    """
    Scenario: dashboard replaces the welcome page when widgets are registered
      Given a StatWidget over the registered report "orders-revenue" is registered before Admin(...)
      When  a signed-in user requests GET {prefix}/
      Then  the page contains data-testid="dashboard-grid"
      And   the page does not contain "Welcome to HyperAdmin Dashboard"
    """
    register_widget(StatWidget(OrderRevenueReport))
    mounted = mount(make_engine(tmp_path))

    home = mounted.client.get("/admin/")
    page = mounted.client.get("/admin/dashboard/")

    assert home.status_code == 200
    assert GRID in home.text
    assert WELCOME not in home.text
    assert 'data-testid="widget-stat-orders-revenue"' in home.text
    assert "/static/plugins/reports/dashboard.css" in home.text
    assert "<title>Dashboard |" in home.text
    assert _order(page.text) == _order(home.text) == ["stat-orders-revenue"]
    assert 'data-testid="nav-dashboard"' not in home.text
    assert mounted.admin.plugins.home_page is not None
    assert mounted.admin.plugins.home_page.plugin == "reports"


def test_welcome_page_stays_when_no_widget_is_registered(tmp_path: Path) -> None:
    """
    Scenario: welcome page stays when no widget is registered
      Given the reports plugin is installed and no widget is registered
      When  a signed-in user requests GET {prefix}/
      Then  the welcome page is shown
      And   GET {prefix}/dashboard/ is 404
    """
    mounted = mount(make_engine(tmp_path))

    home = mounted.client.get("/admin/")

    assert WELCOME in home.text
    assert GRID not in home.text
    assert mounted.client.get("/admin/dashboard/").status_code == 404
    assert mounted.admin.plugins.home_page is None


def test_dashboard_home_false_keeps_the_welcome_page_and_adds_a_sidebar_link(
    tmp_path: Path,
) -> None:
    """
    Scenario: dashboard_home=False keeps the welcome page and adds a sidebar link
      Given widgets are registered and plugin_settings={"reports": {"dashboard_home": False}}
      When  a signed-in user requests GET {prefix}/
      Then  the welcome page is shown
      And   the sidebar has a link data-testid="nav-dashboard" to {prefix}/dashboard/
    """
    mounted, _ = _dashboard(tmp_path, plugin_settings={"reports": {"dashboard_home": False}})

    home = mounted.client.get("/admin/")

    assert WELCOME in home.text
    assert GRID not in home.text
    link = next(tag for tag in home.text.split("<a ") if 'data-testid="nav-dashboard"' in tag)
    assert 'href="/admin/dashboard/"' in link.split(">", 1)[0]
    assert _page_order(mounted, path="/admin/dashboard/") == ["a", "b", "c", "stat-payroll-total"]


def test_loading_a_widget_the_user_may_not_view_is_refused(tmp_path: Path) -> None:
    """
    Scenario: loading a widget the user may not view is refused
      Given user "viewer" lacks view_report_payroll_total
      When  viewer requests GET {prefix}/dashboard/widgets/stat-payroll-total
      Then  the response is 403
    """
    mounted, _ = _dashboard(tmp_path)

    response = mounted.client.get(
        "/admin/dashboard/widgets/stat-payroll-total", headers={"x-user": "viewer"}
    )

    assert response.status_code == 403
    assert 'data-testid="widget-forbidden"' in response.text
    assert "payroll" not in response.text.lower()
    assert _page_order(mounted, user="viewer") == ["a", "b", "c"]


def test_loading_an_unknown_widget_is_not_found(tmp_path: Path) -> None:
    """
    Scenario: loading an unknown widget is not found
      When  a signed-in user requests GET {prefix}/dashboard/widgets/nope
      Then  the response is 404
    """
    mounted, _ = _dashboard(tmp_path)

    assert mounted.client.get("/admin/dashboard/widgets/nope").status_code == 404


def test_saving_an_order_over_htmx_answers_204(tmp_path: Path) -> None:
    """
    Scenario: saving an order over HTMX answers 204
      Given alice sees [A, B, C]
      When  alice POSTs {prefix}/dashboard/layout with widgets=C&widgets=A&widgets=B and
            HX-Request: true
      Then  the response is 204
      And   GET {prefix}/ shows [C, A, B] for alice
    """
    mounted, engine = _dashboard(tmp_path)
    order = ["c", "a", "b", "stat-payroll-total"]

    response = mounted.client.post("/admin/dashboard/layout", data={"widgets": order}, headers=HX)

    assert response.status_code == 204
    assert _page_order(mounted) == order
    assert _page_order(mounted, user="bob") == ["a", "b", "c", "stat-payroll-total"]
    assert _saved(engine, 1) == order


def test_saving_an_invalid_order_is_rejected(tmp_path: Path) -> None:
    """
    Scenario: saving an invalid order is rejected
      Given alice sees [A, B, C]
      When  alice POSTs {prefix}/dashboard/layout with widgets=A&widgets=B&widgets=P
      Then  the response is 400
    """
    mounted, engine = _dashboard(tmp_path)

    response = mounted.client.post(
        "/admin/dashboard/layout",
        data={"widgets": ["a", "b", "stat-payroll-total"]},
        headers={"x-user": "viewer", **HX},
    )

    assert response.status_code == 400
    assert _saved(engine, 3) is None


def test_saving_a_layout_without_a_signed_in_user_is_refused(tmp_path: Path) -> None:
    """
    Scenario: saving a layout without a signed-in user is refused
      Given the admin has no authentication configured
      When  POST {prefix}/dashboard/layout with widgets=A&widgets=B&widgets=C
      Then  the response is 403
    """
    mounted, _ = _dashboard(tmp_path, auth=False)
    page = mounted.client.get("/admin/")

    response = mounted.client.post(
        "/admin/dashboard/layout", data={"widgets": ["a", "b", "c", "stat-payroll-total"]}
    )

    assert response.status_code == 403
    assert _order(page.text) == ["a", "b", "c", "stat-payroll-total"]
    assert 'data-testid="widget-move-up"' not in page.text
    assert 'data-testid="dashboard-reset"' not in page.text
    for path in ("/admin/dashboard/layout/move", "/admin/dashboard/reset"):
        refused = mounted.client.post(path, data={"key": "b", "direction": "up"})
        assert refused.status_code == 403


def test_saving_with_a_missing_layout_table_answers_503(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: saving with a missing layout table answers 503
      Given the layout table does not exist
      When  alice POSTs {prefix}/dashboard/layout with her visible keys
      Then  the response is 503
    """
    mounted, _ = _dashboard(tmp_path, layouts=False)
    order = ["c", "a", "b", "stat-payroll-total"]

    with caplog.at_level(logging.WARNING, logger="hyperadmin_reports.dashboard.service"):
        saved = mounted.client.post("/admin/dashboard/layout", data={"widgets": order}, headers=HX)
        moved = mounted.client.post(
            "/admin/dashboard/layout/move", data={"key": "b", "direction": "up"}, headers=HX
        )
        page = mounted.client.get("/admin/")
        reset = mounted.client.post("/admin/dashboard/reset", headers=HX)

    assert saved.status_code == moved.status_code == 503
    assert _order(page.text) == ["a", "b", "c", "stat-payroll-total"]
    assert 'data-testid="widget-move-up"' not in page.text
    assert 'data-testid="widget-drag-handle"' not in page.text
    assert 'data-testid="dashboard-reset"' not in page.text
    assert reset.status_code == 200
    warnings = [r for r in caplog.records if r.name == "hyperadmin_reports.dashboard.service"]
    assert len(warnings) == 1
    assert LAYOUT_TABLE_NAME in warnings[0].getMessage()


def test_a_plain_form_move_redirects_back_to_the_dashboard(tmp_path: Path) -> None:
    """
    Scenario: a plain form move redirects back to the dashboard
      Given alice sees [A, B, C]
      When  alice POSTs {prefix}/dashboard/layout/move with key=B&direction=up without HX-Request
      Then  the response is a 303 redirect to {prefix}/dashboard/
      And   alice's order is [B, A, C]
    """
    mounted, engine = _dashboard(tmp_path)

    response = mounted.client.post(
        "/admin/dashboard/layout/move", data={"key": "b", "direction": "up"}
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard/"
    assert _saved(engine, 1) == ["b", "a", "c", "stat-payroll-total"]
    assert _page_order(mounted) == ["b", "a", "c", "stat-payroll-total"]


def test_reset_over_htmx_returns_the_default_grid(tmp_path: Path) -> None:
    """
    Scenario: reset over HTMX returns the default grid
      Given alice saved [C, A, B]
      When  alice POSTs {prefix}/dashboard/reset with HX-Request: true
      Then  the response is the grid in the order [A, B, C]
    """
    mounted, engine = _dashboard(tmp_path)
    order = ["c", "a", "b", "stat-payroll-total"]
    mounted.client.post("/admin/dashboard/layout", data={"widgets": order}, headers=HX)
    assert _page_order(mounted) == order

    response = mounted.client.post("/admin/dashboard/reset", headers=HX)

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<div id="dashboard-grid"')
    assert "<html" not in response.text
    assert _order(response.text) == ["a", "b", "c", "stat-payroll-total"]
    assert _saved(engine, 1) is None


def test_plain_form_posts_redirect_and_htmx_posts_answer_with_the_grid(tmp_path: Path) -> None:
    """
    Scenario: every layout POST has an HTMX and a plain-form answer
      Given alice sees [A, B, C, payroll]
      When  she saves an order and resets with plain forms, and moves B up over HTMX
      Then  the plain posts answer 303 to {prefix}/dashboard/
      And   the HTMX move answers with the grid, naming the moved card and its new position
    """
    mounted, engine = _dashboard(tmp_path)
    order = ["c", "a", "b", "stat-payroll-total"]

    saved = mounted.client.post("/admin/dashboard/layout", data={"widgets": order})
    reset = mounted.client.post("/admin/dashboard/reset")
    moved = mounted.client.post(
        "/admin/dashboard/layout/move", data={"key": "b", "direction": "up"}, headers=HX
    )

    assert (saved.status_code, saved.headers["location"]) == (303, "/admin/dashboard/")
    assert (reset.status_code, reset.headers["location"]) == (303, "/admin/dashboard/")
    assert moved.status_code == 200
    assert _order(moved.text) == ["b", "a", "c", "stat-payroll-total"]
    assert 'data-moved-key="b"' in moved.text
    assert 'data-moved-direction="up"' in moved.text
    assert 'data-announce="Moved B to position 1 of 4"' in moved.text
    assert "<html" not in moved.text
    assert _saved(engine, 1) == ["b", "a", "c", "stat-payroll-total"]


def test_a_move_with_an_unknown_key_or_direction_is_rejected(tmp_path: Path) -> None:
    """
    Scenario: POST move with an unknown key or a bad direction is rejected
      Given alice sees [A, B, C, payroll]
      When  she POSTs a move for "nope", a move "left" and a move without fields
      Then  each response is 400 and nothing is saved
    """
    mounted, engine = _dashboard(tmp_path)

    for data in ({"key": "nope", "direction": "up"}, {"key": "a", "direction": "left"}, {}):
        response = mounted.client.post("/admin/dashboard/layout/move", data=data, headers=HX)
        assert response.status_code == 400

    assert _saved(engine, 1) is None


def test_an_htmx_request_for_the_grid_gets_only_the_grid(tmp_path: Path) -> None:
    """
    Scenario: the dashboard page answers a grid-targeted HTMX request with the grid
      Given alice sees the dashboard
      When  GET {prefix}/dashboard/ arrives with HX-Request and HX-Target: dashboard-grid
      Then  the response is the grid fragment
      And   an HTMX request with another target still gets the full page
    """
    mounted, _ = _dashboard(tmp_path)

    grid = mounted.client.get("/admin/dashboard/", headers={**HX, "HX-Target": "dashboard-grid"})
    page = mounted.client.get("/admin/dashboard/", headers={**HX, "HX-Target": "main-content"})

    assert grid.text.lstrip().startswith('<div id="dashboard-grid"')
    assert "<html" not in grid.text
    assert "<html" in page.text


def test_dashboard_layouts_off_serves_the_default_order_without_controls(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: dashboard_layouts=False hides reordering and never touches the table
      Given plugin_settings={"reports": {"dashboard_layouts": False}} and no layout table
      When  alice opens the dashboard and POSTs an order
      Then  the widgets render in the default order without controls
      And   the POST answers 503 and no warning is logged
    """
    mounted, _ = _dashboard(
        tmp_path, layouts=False, plugin_settings={"reports": {"dashboard_layouts": False}}
    )

    with caplog.at_level(logging.WARNING, logger="hyperadmin_reports.dashboard.service"):
        page = mounted.client.get("/admin/")
        response = mounted.client.post(
            "/admin/dashboard/layout",
            data={"widgets": ["c", "a", "b", "stat-payroll-total"]},
            headers=HX,
        )

    assert _order(page.text) == ["a", "b", "c", "stat-payroll-total"]
    assert 'data-testid="widget-move-up"' not in page.text
    assert response.status_code == 503
    assert [r for r in caplog.records if r.name.startswith("hyperadmin_reports")] == []


def test_a_custom_dashboard_prefix_moves_the_page(tmp_path: Path) -> None:
    """
    Scenario: dashboard_prefix renames the page prefix
      Given plugin_settings={"reports": {"dashboard_prefix": "/home"}}
      When  alice requests {prefix}/home/ and {prefix}/dashboard/
      Then  the dashboard is at {prefix}/home/ and {prefix}/dashboard/ is 404
      And   the card's move form posts to {prefix}/home/layout/move
    """
    mounted, _ = _dashboard(tmp_path, plugin_settings={"reports": {"dashboard_prefix": "/home"}})

    page = mounted.client.get("/admin/home/")

    assert GRID in page.text
    assert 'action="/admin/home/layout/move"' in page.text
    assert 'hx-get="/admin/home/widgets/a"' in page.text
    assert mounted.client.get("/admin/dashboard/").status_code == 404


def test_the_vendored_library_is_served_with_the_plugins_static_files(tmp_path: Path) -> None:
    """
    Scenario: the vendored library is served with the plugin's static files
      When  GET {prefix}/static/plugins/reports/vendor/sortable-1.15.6.min.js
      Then  the response is 200
      And   the file is the unmodified minified build of the 1.15.6 release, with its licence
    """
    mounted, _ = _dashboard(tmp_path)

    response = mounted.client.get(SORTABLE_PATH)

    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == SORTABLE_SHA256
    assert response.content.startswith(b"/*! Sortable 1.15.6 - MIT")
    licence = (STATIC_DIR / "vendor" / "LICENSE-sortablejs.txt").read_text()
    assert licence.startswith("MIT License")
    assert mounted.client.get("/admin/static/plugins/reports/dashboard.js").status_code == 200


def test_the_reorder_scripts_load_only_when_controls_are_rendered(tmp_path: Path) -> None:
    """
    Scenario: the drag and drop scripts load only with the reorder controls
      Given alice, who can save an order, and nobody, who may view no widget
      When  each opens the dashboard
      Then  the signed-in page loads SortableJS and dashboard.js with defer and no inline script
      And   nobody's page, which has no controls, loads neither
    """
    signed_in, _ = _dashboard(tmp_path)
    page = signed_in.client.get("/admin/").text
    content = page.split('data-testid="page-header"', 1)[1].split("</main>", 1)[0]

    assert f'<script src="http://testserver{SORTABLE_PATH}" defer></script>' in content
    assert 'src="http://testserver/admin/static/plugins/reports/dashboard.js" defer' in content
    assert content.count("<script") == 2
    assert 'data-layout-url="/admin/dashboard/layout"' in content
    assert 'data-moved="Moved __title__ to position __position__ of __total__"' in content
    handle = next(tag for tag in content.split("<button ") if "data-drag-handle" in tag)
    assert 'type="button"' in handle
    assert 'aria-label="Drag to reorder A"' in handle
    assert 'data-testid="widget-drag-handle"' in handle

    empty = signed_in.client.get("/admin/", headers={"x-user": "nobody"}).text
    assert "sortable-1.15.6.min.js" not in empty
    assert "dashboard.js" not in empty
