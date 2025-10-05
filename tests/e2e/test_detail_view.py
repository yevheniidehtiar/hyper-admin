"""End-to-end tests for detail view functionality."""

from playwright.sync_api import Page, expect


def test_detail_view_loads_correctly(page: Page, demo_base_url: str) -> None:
    """Test that the detail view loads with correct data and actions."""
    page.goto(f"{demo_base_url}/admin/user")

    # Click the "View" link for the first user in the list
    first_view_link = page.locator('a:has-text("View")').first
    expect(first_view_link).to_be_visible()

    # Get the id from the href
    href = first_view_link.get_attribute("href")
    item_id = href.split("/")[-1]

    first_view_link.click()

    # Check that the URL is correct
    expect(page).to_have_url(f"{demo_base_url}/admin/user/{item_id}")

    # Check that the page title is correct
    expect(page).to_have_title(f"User #{item_id} | HyperAdmin")

    # Check that the main heading is correct
    expect(page.locator("h1")).to_have_text(f"User #{item_id}")

    # Check that all fields are displayed and are read-only
    expect(page.locator('input[name="id"]')).to_be_visible()
    expect(page.locator('input[name="id"]')).not_to_be_editable()
    expect(page.locator('input[name="name"]')).to_be_visible()
    expect(page.locator('input[name="name"]')).not_to_be_editable()
    expect(page.locator('input[name="email"]')).to_be_visible()
    expect(page.locator('input[name="email"]')).not_to_be_editable()

    # Check for Update and Delete buttons
    update_link = page.locator('a:has-text("Update")')
    expect(update_link).to_be_visible()
    expect(update_link).to_have_attribute("href", "./update")

    delete_button = page.locator('button:has-text("Delete")')
    expect(delete_button).to_be_visible()
    expect(delete_button).to_have_attribute("hx-post", "./delete")
    expect(delete_button).to_have_attribute("hx-target", "body")

    # Check for the "Back to list" link
    back_link = page.locator('a:has-text("Back to list")')
    expect(back_link).to_be_visible()
    expect(back_link).to_have_attribute("href", "../")
