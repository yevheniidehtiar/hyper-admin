import re

from playwright.sync_api import Page, expect


def test_create_user_form_rendering(page: Page, demo_base_url: str):
    """Test that the create form for User model is rendered correctly."""
    page.goto(f"{demo_base_url}/admin/user/create")
    expect(page).to_have_title("HyperAdmin")
    h2 = page.locator("h2")
    expect(h2).to_be_visible()
    expect(h2).to_have_text("Create User")
    expect(page.locator(f'form[hx-post="{demo_base_url}/admin/user"]')).to_be_visible()
    expect(page.locator('label[for="name"]')).to_have_text("Name")
    expect(page.locator('input[name="name"]')).to_be_visible()
    expect(page.locator('label[for="is_active"]')).to_have_text("Is Active")
    expect(page.locator('input[name="is_active"][type="checkbox"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_have_text("Create")


def test_create_user_validation_error(page: Page, demo_base_url: str):
    """Test that submitting an invalid form for User model shows an error message."""
    page.goto(f"{demo_base_url}/admin/user/create")
    page.locator('button[type="submit"]').click()

    validation_error = page.locator(".mb-4").locator("ul.text-red-500")
    expect(validation_error).to_be_visible()
    expect(validation_error).to_contain_text("String should have at least 1 character")


def test_create_user_successful_submission(page: Page, demo_base_url: str):
    """Test that successful submission for User model redirects to the detail page."""
    page.goto(f"{demo_base_url}/admin/user/create")
    page.locator('input[name="name"]').fill("Test User")
    page.locator('input[name="is_active"]').check()
    page.locator('button[type="submit"]').click()

    # The redirect is handled by HTMX, so we need to wait for the URL to change.
    expect(page).to_have_url(re.compile(r".*/admin/user/\d+"))
    expect(page.get_by_role("heading", name=re.compile(r"User #"))).to_contain_text("User #")
    expect(page.locator("dd")).to_contain_text("Test User")
    expect(page.locator("dd")).to_contain_text("True")
