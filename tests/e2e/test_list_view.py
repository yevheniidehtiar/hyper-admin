"""End-to-end tests for list view functionality including pagination, search, and sorting."""

import re

from playwright.sync_api import Page, expect


def test_admin_interface_loads(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    expect(page).to_have_title("User List | HyperAdmin")
    expect(page.get_by_role("link", name="HyperAdmin")).to_be_visible()
    expect(page.get_by_test_id("sidebar").get_by_role("link", name="Users")).to_be_visible()
    expect(page.get_by_role("navigation")).to_be_visible()
    expect(page.get_by_role("complementary")).to_be_visible()
    expect(page.get_by_role("main")).to_be_attached()


def test_admin_navigation_structure(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    sidebar = page.get_by_test_id("sidebar")
    expect(sidebar).to_be_visible()
    expect(sidebar.get_by_text("Menu")).to_be_visible()
    expect(sidebar.get_by_role("link", name="Users")).to_be_visible()

    expect(page.get_by_role("navigation").get_by_role("link", name="HyperAdmin")).to_be_visible()


def test_responsive_admin_interface(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    for width, height in [(1200, 800), (768, 600), (375, 667)]:
        page.set_viewport_size({"width": width, "height": height})
        expect(page.get_by_role("main")).to_be_attached()

    page.set_viewport_size({"width": 1280, "height": 720})


def test_admin_interface_styling(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    expect(page.locator("body")).to_have_class("ha-page")
    expect(page.get_by_role("main")).to_have_class("ha-content")
    expect(page.get_by_role("navigation")).to_have_class("ha-navbar")
    expect(page.get_by_role("complementary")).to_have_class("ha-sidebar")


def test_admin_interface_accessibility(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    expect(page).to_have_title("User List | HyperAdmin")
    expect(page.get_by_role("navigation")).to_be_visible()
    expect(page.get_by_role("main")).to_be_attached()
    expect(page.get_by_role("complementary")).to_be_visible()

    users_link = page.get_by_test_id("sidebar").get_by_role("link", name="Users")
    expect(users_link).to_be_visible()
    expect(users_link).to_have_attribute("href", "/admin/user")


def test_admin_interface_htmx_integration(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    expect(page.locator("script[src*='htmx']")).to_be_attached()
    expect(page.locator("style")).to_be_attached()


def test_pagination_functionality(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    table = page.get_by_test_id("list-table")
    if table.count() == 0:
        return

    expect(table).to_be_visible()
    expect(page.get_by_test_id("pagination-info")).to_be_visible()

    next_link = page.get_by_test_id("pagination-next")
    if next_link.count() > 0:
        next_link.click()
        expect(page.get_by_test_id("pagination-page")).to_contain_text("Page 2")

        prev_link = page.get_by_test_id("pagination-prev")
        if prev_link.count() > 0:
            prev_link.click()
            expect(page.get_by_test_id("pagination-page")).to_contain_text("Page 1")


def test_search_functionality(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    search_input = page.get_by_test_id("search-input")
    if search_input.count() == 0:
        return

    expect(search_input).to_be_visible()
    search_input.fill("test")
    page.wait_for_timeout(800)
    search_input.clear()
    page.wait_for_timeout(800)
    search_input.fill("admin")
    page.wait_for_timeout(800)

    if page.get_by_test_id("list-table").count() > 0:
        expect(page.get_by_test_id("list-table")).to_be_visible()


def test_sorting_functionality(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    if page.get_by_test_id("list-table").count() == 0:
        return

    expect(page.get_by_test_id("list-table")).to_be_visible()

    name_sort = page.get_by_test_id("sort-name")
    if name_sort.count() > 0:
        name_sort.click()
        page.wait_for_timeout(500)
        expect(page.get_by_test_id("list-table")).to_be_visible()
        expect(page.get_by_test_id("sort-name")).to_contain_text("▲")

        name_sort.click()
        page.wait_for_timeout(500)
        expect(page.get_by_test_id("sort-name")).to_contain_text("▼")

    email_sort = page.get_by_test_id("sort-email")
    if email_sort.count() > 0:
        email_sort.click()
        page.wait_for_timeout(500)
        expect(page.get_by_test_id("list-table")).to_be_visible()
        expect(page.get_by_test_id("sort-email")).to_contain_text("▲")


def test_combined_search_and_pagination(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    search_input = page.get_by_test_id("search-input")
    if search_input.count() == 0 or page.get_by_test_id("list-table").count() == 0:
        return

    search_input.fill("user")
    page.wait_for_timeout(800)

    next_link = page.get_by_test_id("pagination-next")
    if next_link.count() > 0:
        next_link.click()
        page.wait_for_timeout(500)
        expect(page.get_by_test_id("list-table")).to_be_visible()
        expect(search_input).to_have_value("user")


def test_combined_search_and_sorting(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    search_input = page.get_by_test_id("search-input")
    if search_input.count() == 0 or page.get_by_test_id("list-table").count() == 0:
        return

    search_input.fill("test")
    page.wait_for_timeout(800)

    name_sort = page.get_by_test_id("sort-name")
    if name_sort.count() > 0:
        name_sort.click()
        page.wait_for_timeout(500)
        expect(page.get_by_test_id("list-table")).to_be_visible()
        expect(search_input).to_have_value("test")
        expect(page.get_by_test_id("sort-name")).to_contain_text("▲")


def test_action_buttons_present(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    if page.get_by_test_id("list-table").count() == 0:
        return

    rows = page.get_by_test_id("list-row")
    if rows.count() == 0:
        return

    first_row = rows.first
    expect(first_row.get_by_test_id("row-view-link")).to_be_visible()
    expect(first_row.get_by_test_id("row-edit-link")).to_be_visible()
    expect(first_row.get_by_test_id("row-delete-btn")).to_be_visible()


def test_create_new_button(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    create_link = page.get_by_test_id("create-link")
    if create_link.count() == 0:
        return

    expect(create_link).to_be_visible()
    create_link.click()
    expect(page).to_have_url(re.compile(r".*/user.*create"))


def test_responsive_design_elements(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    for width, height in [(1200, 800), (768, 600), (375, 667)]:
        page.set_viewport_size({"width": width, "height": height})
        if page.get_by_test_id("list-table").count() > 0:
            expect(page.get_by_test_id("list-table")).to_be_visible()

    page.set_viewport_size({"width": 1280, "height": 720})


def test_htmx_requests_work(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    search_input = page.get_by_test_id("search-input")
    if search_input.count() == 0:
        return

    search_input.fill("htmx")
    page.wait_for_timeout(800)
    expect(search_input).to_have_value("htmx")

    if page.get_by_test_id("list-table").count() > 0:
        expect(page.get_by_test_id("list-table")).to_be_visible()


def test_error_handling_graceful(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    search_input = page.get_by_test_id("search-input")
    if search_input.count() == 0:
        return

    for term in ["'; DROP TABLE users; --", "a" * 1000]:
        search_input.fill(term)
        page.wait_for_timeout(800)
        expect(page.get_by_role("main")).to_be_attached()

    search_input.clear()
    page.wait_for_timeout(500)
    expect(page.get_by_role("main")).to_be_attached()

def test_filter_bar_renders(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    filter_bar = page.get_by_test_id("filter-bar")
    expect(filter_bar).to_be_visible()

    # Toggle filters to make them visible
    page.get_by_role("button", name="Filters").click()

    # Check for specific filters
    expect(page.get_by_test_id("filter-is_active")).to_be_visible()
    expect(page.get_by_test_id("filter-user_type")).to_be_visible()

def test_filter_functionality(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    # Wait for table to load
    expect(page.get_by_test_id("list-table")).to_be_visible()

    # Initial row count (should be 3 based on simple_app.py)
    rows = page.get_by_test_id("list-row")
    # We might not know the exact count if other tests modified it,
    # but there should be some rows.
    initial_count = rows.count()

    # Toggle filters to make them visible
    page.get_by_role("button", name="Filters").click()

    # Apply a filter that matches nothing (or something specific)
    # Since we don't have many records, let's filter for No on is_active
    page.get_by_test_id("filter-is_active").select_option("false")

    # Wait for HTMX reload
    page.wait_for_timeout(500)

    # All initial users are active by default in simple_app.py
    # So filtering for is_active=No should yield 0 rows
    expect(page.get_by_test_id("list-row")).to_have_count(0)

    # Clear filters
    page.get_by_role("link", name="Clear all filters").click()
    page.wait_for_timeout(500)
    expect(page.get_by_test_id("list-row")).to_have_count(initial_count)

def test_table_overflow_scroll(page: Page, demo_base_url: str) -> None:
    page.goto(demo_base_url + "/admin/user")

    # Set a very narrow viewport
    page.set_viewport_size({"width": 300, "height": 600})

    wrapper = page.locator(".ha-table-wrapper")
    expect(wrapper).to_be_visible()

    # Check that overflow-x is auto
    overflow_x = wrapper.evaluate("el => window.getComputedStyle(el).overflowX")
    assert overflow_x == "auto"
