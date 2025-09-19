from playwright.sync_api import Page, expect


def test_create_group(page: Page):
    """Test creating a new group with valid data."""
    page.goto("http://localhost:8000/admin/group/create")

    # Fill out the form
    page.fill("input[name='name']", "Test Group")
    page.fill("input[name='description']", "A group for testing purposes.")
    page.check("input[name='is_active']")

    # Submit the form
    page.click("button[type='submit']")

    # Check for redirection to the detail page
    expect(page).to_have_url(r"http://localhost:8000/admin/group/\d+")

    # Check that the new group's data is displayed
    expect(page.locator("body")).to_contain_text("Test Group")
    expect(page.locator("body")).to_contain_text("A group for testing purposes.")


def test_create_group_invalid_data(page: Page):
    """Test creating a new group with invalid data."""
    page.goto("http://localhost:8000/admin/group/create")

    # Submit the form with an empty name
    page.click("button[type='submit']")

    # Check that the form is re-rendered with a validation error
    expect(page.locator(".invalid-feedback")).to_be_visible()
    expect(page.locator(".invalid-feedback")).to_contain_text("String should have at least 1 character")
