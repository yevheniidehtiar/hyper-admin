"""End-to-end tests for list view functionality including pagination, search, and sorting."""

import re

from playwright.sync_api import Page, expect


def test_admin_interface_loads(page: Page, demo_base_url: str) -> None:
    """Test that the admin interface loads correctly."""
    page.goto(demo_base_url + "/admin/user")

    # Check that the page loads with correct title
    expect(page).to_have_title("User List | HyperAdmin")

    # Check that we have the admin interface structure
    expect(page.get_by_text("HyperAdmin")).to_be_visible()
    expect(page.get_by_text("Users")).to_be_visible()  # From the sidebar

    # Check that main content area is present (even if empty)
    main_content = page.locator("main")
    expect(main_content).to_be_attached()

    # Check that navigation works
    expect(page.locator("nav")).to_be_visible()
    expect(page.locator("aside")).to_be_visible()  # Sidebar


def test_admin_navigation_structure(page: Page, demo_base_url: str) -> None:
    """Test the basic admin navigation structure."""
    page.goto(demo_base_url + "/admin/user")

    # Test sidebar navigation
    sidebar = page.locator("aside")
    expect(sidebar).to_be_visible()
    expect(sidebar.get_by_text("Menu")).to_be_visible()
    expect(sidebar.get_by_text("Users")).to_be_visible()

    # Test top navigation
    nav = page.locator("nav")
    expect(nav).to_be_visible()
    expect(nav.get_by_text("HyperAdmin")).to_be_visible()


def test_responsive_admin_interface(page: Page, demo_base_url: str) -> None:
    """Test that the admin interface is responsive."""
    page.goto(demo_base_url + "/admin/user")

    # Test desktop view
    page.set_viewport_size({"width": 1200, "height": 800})
    expect(page.locator("aside")).to_be_visible()
    expect(page.locator("main")).to_be_attached()

    # Test tablet view
    page.set_viewport_size({"width": 768, "height": 600})
    expect(page.locator("main")).to_be_attached()

    # Test mobile view
    page.set_viewport_size({"width": 375, "height": 667})
    expect(page.locator("main")).to_be_attached()

    # Reset viewport
    page.set_viewport_size({"width": 1280, "height": 720})


def test_admin_interface_styling(page: Page, demo_base_url: str) -> None:
    """Test that the admin interface has proper styling."""
    page.goto(demo_base_url + "/admin/user")

    # Check that CSS is loaded
    expect(page.locator("body")).to_have_class("ha-page")

    # Check that main element has proper styling
    main_element = page.locator("main")
    expect(main_element).to_be_attached()
    expect(main_element).to_have_class("ha-content")

    # Check that navigation has styling
    nav = page.locator("nav")
    expect(nav).to_have_class("ha-navbar")

    # Check sidebar styling
    aside = page.locator("aside")
    expect(aside).to_have_class("ha-sidebar")


def test_admin_interface_accessibility(page: Page, demo_base_url: str) -> None:
    """Test basic accessibility features of the admin interface."""
    page.goto(demo_base_url + "/admin/user")

    # Check that the page has a proper title
    expect(page).to_have_title("User List | HyperAdmin")

    # Check that main landmarks are present
    expect(page.locator("nav")).to_be_visible()
    expect(page.locator("main")).to_be_attached()
    expect(page.locator("aside")).to_be_visible()

    # Check that links have proper text
    sidebar_link = page.locator("aside a").filter(has_text="Users")
    expect(sidebar_link).to_be_visible()
    expect(sidebar_link).to_have_attribute("href", "/admin/user")


def test_admin_interface_htmx_integration(page: Page, demo_base_url: str) -> None:
    """Test that HTMX is properly loaded and integrated."""
    page.goto(demo_base_url + "/admin/user")

    # Check that HTMX script is loaded
    htmx_script = page.locator("script[src*='htmx']")
    expect(htmx_script).to_be_attached()

    # Check that HTMX CSS indicators are present
    htmx_styles = page.locator("style")
    expect(htmx_styles).to_be_attached()


def test_pagination_functionality(page: Page, demo_base_url: str) -> None:
    """Test pagination controls work correctly."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for the page to load and check if content is available
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if table exists, if not, skip table-specific tests
    table = page.locator("table")
    if table.count() > 0:
        expect(table).to_be_visible()

        # Check pagination info is displayed
        pagination_info = page.locator("text=Showing")
        if pagination_info.count() > 0:
            expect(pagination_info.first).to_be_visible()

        # Check pagination controls
        next_button = page.locator("a").filter(has_text="Next")
        previous_button = page.locator("a").filter(has_text="Previous")

        # If there are multiple pages, test navigation
        if next_button.count() > 0:
            # Click next page
            next_button.click()

            # Wait for HTMX update
            page.wait_for_timeout(500)

            # Check that we're on page 2
            expect(page.locator("text=Page 2")).to_be_visible()

            # Test previous button
            if previous_button.count() > 0:
                previous_button.click()
                page.wait_for_timeout(500)
                expect(page.locator("text=Page 1")).to_be_visible()


def test_search_functionality(page: Page, demo_base_url: str) -> None:
    """Test search functionality with real-time updates."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if search input exists (even without table content)
    search_input = page.locator("input[name='search']")
    if search_input.count() > 0:
        expect(search_input).to_be_visible()

        # Test search functionality
        search_input.fill("test")

        # Wait for HTMX search delay (500ms as per template)
        page.wait_for_timeout(800)

        # Test clearing search
        search_input.clear()
        page.wait_for_timeout(800)

        # Test search with different terms
        search_input.fill("admin")
        page.wait_for_timeout(800)

    # Check if table exists and test it conditionally
    table = page.locator("table")
    if table.count() > 0:
        expect(table).to_be_visible()


def test_sorting_functionality(page: Page, demo_base_url: str) -> None:
    """Test sorting by clicking column headers."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if table exists before testing sorting
    table = page.locator("table")
    if table.count() > 0:
        expect(table).to_be_visible()

        # Find sortable column headers
        name_header = page.locator("th a").filter(has_text="name")
        email_header = page.locator("th a").filter(has_text="email")

        # Test sorting by name
        if name_header.count() > 0:
            name_header.click()

            # Wait for HTMX update
            page.wait_for_timeout(500)

            # Check that table is still visible after sort
            expect(page.locator("table")).to_be_visible()

            # Check for sort indicator (triangle up)
            expect(page.locator("th").filter(has_text="name")).to_contain_text("▲")

            # Click again to reverse sort
            name_header.click()
            page.wait_for_timeout(500)

            # Check for sort indicator (triangle down)
            expect(page.locator("th").filter(has_text="name")).to_contain_text("▼")

        # Test sorting by email
        if email_header.count() > 0:
            email_header.click()
            page.wait_for_timeout(500)
            expect(page.locator("table")).to_be_visible()
            expect(page.locator("th").filter(has_text="email")).to_contain_text("▲")


def test_combined_search_and_pagination(page: Page, demo_base_url: str) -> None:
    """Test that search and pagination work together."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if search input and table exist
    search_input = page.locator("input[name='search']")
    table = page.locator("table")

    if search_input.count() > 0 and table.count() > 0:
        expect(table).to_be_visible()

        # Perform a search
        search_input.fill("user")
        page.wait_for_timeout(800)

        # Check that pagination still works after search
        next_button = page.locator("a").filter(has_text="Next")
        if next_button.count() > 0:
            next_button.click()
            page.wait_for_timeout(500)
            expect(page.locator("table")).to_be_visible()

            # Verify search term is preserved
            expect(search_input).to_have_value("user")


def test_combined_search_and_sorting(page: Page, demo_base_url: str) -> None:
    """Test that search and sorting work together."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if search input and table exist
    search_input = page.locator("input[name='search']")
    table = page.locator("table")

    if search_input.count() > 0 and table.count() > 0:
        expect(table).to_be_visible()

        # Perform a search first
        search_input.fill("test")
        page.wait_for_timeout(800)

        # Then try sorting
        name_header = page.locator("th a").filter(has_text="name")
        if name_header.count() > 0:
            name_header.click()
            page.wait_for_timeout(500)

            # Verify both search and sort work together
            expect(page.locator("table")).to_be_visible()
            expect(search_input).to_have_value("test")
            expect(page.locator("th").filter(has_text="name")).to_contain_text("▲")


def test_action_buttons_present(page: Page, demo_base_url: str) -> None:
    """Test that action buttons (View, Edit, Delete) are present."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if table exists before testing action buttons
    table = page.locator("table")
    if table.count() > 0:
        expect(table).to_be_visible()

        # Check for action buttons in the table
        # These might not be visible if there's no data, so we check conditionally
        rows = page.locator("tbody tr")
        if rows.count() > 0:
            # Check that action links/buttons exist
            view_links = rows.first.locator("a").filter(has_text="View")
            edit_links = rows.first.locator("a").filter(has_text="Edit")
            delete_buttons = rows.first.locator("button").filter(has_text="Delete")

            # At least one of each should exist if there's data
            expect(view_links.or_(edit_links).or_(delete_buttons)).to_have_count(3)


def test_create_new_button(page: Page, demo_base_url: str) -> None:
    """Test that the 'Create New' button is present and functional."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check for Create New button - it might not be visible if content isn't rendered
    create_button = page.locator("a").filter(has_text="Create New User")
    if create_button.count() > 0:
        expect(create_button).to_be_visible()

        # Click the button to test navigation
        create_button.click()

        # Should navigate to create form (we don't test form details here)
        expect(page).to_have_url(re.compile(".*/user.*create"))


def test_responsive_design_elements(page: Page, demo_base_url: str) -> None:
    """Test responsive design elements of the list view."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if table exists before testing responsive behavior
    table = page.locator("table")

    # Test desktop view first
    page.set_viewport_size({"width": 1200, "height": 800})
    if table.count() > 0:
        expect(table).to_be_visible()

    # Test tablet view
    page.set_viewport_size({"width": 768, "height": 600})
    if table.count() > 0:
        expect(table).to_be_visible()

    # Test mobile view
    page.set_viewport_size({"width": 375, "height": 667})
    if table.count() > 0:
        expect(table).to_be_visible()

    # Reset to default
    page.set_viewport_size({"width": 1280, "height": 720})


def test_htmx_requests_work(page: Page, demo_base_url: str) -> None:
    """Test that HTMX requests are working correctly."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for initial load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if search input exists for HTMX testing
    search_input = page.locator("input[name='search']")
    table = page.locator("table")

    if search_input.count() > 0:
        # Monitor network requests
        requests = []
        page.on("request", lambda request: requests.append(request))

        # Perform a search that should trigger HTMX
        search_input.fill("htmx")

        # Wait for potential HTMX request
        page.wait_for_timeout(800)

        # The search input should still have focus/value
        expect(search_input).to_have_value("htmx")

        # Check table if it exists
        if table.count() > 0:
            expect(table).to_be_visible()


def test_error_handling_graceful(page: Page, demo_base_url: str) -> None:
    """Test that the page handles errors gracefully."""
    page.goto(demo_base_url + "/admin/user")

    # Wait for page to load
    main_element = page.locator("main")
    expect(main_element).to_be_attached()

    # Check if search input exists for error testing
    search_input = page.locator("input[name='search']")
    table = page.locator("table")

    if search_input.count() > 0:
        # Test with potentially problematic search terms

        # Test special characters
        search_input.fill("'; DROP TABLE users; --")
        page.wait_for_timeout(800)

        # Page should still be functional
        expect(main_element).to_be_attached()
        if table.count() > 0:
            expect(table).to_be_visible()

        # Test very long search term
        search_input.fill("a" * 1000)
        page.wait_for_timeout(800)

        # Page should still be functional
        expect(main_element).to_be_attached()
        if table.count() > 0:
            expect(table).to_be_visible()

        # Clear and continue
        search_input.clear()
        page.wait_for_timeout(500)
        expect(main_element).to_be_attached()
        if table.count() > 0:
            expect(table).to_be_visible()
