from playwright.sync_api import Page, expect


def test_admin_dashboard_loads_correctly(page: Page, demo_base_url):
    """Test that the admin dashboard loads correctly and displays expected content."""
    page.goto(f"{demo_base_url}/admin/")

    # Expect a successful response
    expect(page).to_have_url(f"{demo_base_url}/admin/")
    expect(page.locator("h1")).to_have_text("Welcome to HyperAdmin Dashboard")

    # Verify that the navbar and sidebar are present
    expect(page.locator("nav")).to_be_visible()
    expect(page.locator("aside")).to_be_visible()
