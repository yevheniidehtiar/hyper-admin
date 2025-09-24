import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="function")
def debug_page(page: Page):
    # List to store network requests and responses
    network_logs = []

    # Listen for all requests and responses
    page.on("request", lambda request: print(f"Request: {request.method} {request.url}"))
    page.on(
        "response",
        lambda response: network_logs.append(
            {
                "url": response.url,
                "status": response.status,
                "headers": response.all_headers(),
                "body": response.text() if response.status < 400 else f"Error: {response.status}",
                # Only capture body for successful responses to avoid large logs
            }
        ),
    )
    return page


def test_create_user_form_rendering(page: Page, demo_base_url: str):
    """Test that the create form for User model is rendered correctly."""
    page.goto(f"{demo_base_url}/admin/user/create")
    expect(page).to_have_title("HyperAdmin")
    expect(page.locator("h2").filter(has_text="Create User")).to_be_visible()
    expect(page.locator(f'form[hx-post="{demo_base_url}/admin/user"]')).to_be_visible()
    expect(page.locator('label[for="name"]')).to_have_text("Name*")
    expect(page.locator('input[name="name"]')).to_be_visible()
    expect(page.locator('label[for="email"]')).to_have_text("Email*")
    expect(page.locator('input[name="email"]')).to_be_visible()
    expect(page.locator('label[for="is_active"]')).to_have_text("Is active*")
    expect(page.locator('input[name="is_active"][type="checkbox"]')).to_be_visible()
    expect(page.locator('label[for="rating"]')).to_have_text("Rating*")
    expect(page.locator('input[name="rating"][type="number"]')).to_be_visible()
    expect(page.locator('label[for="user_type"]')).to_have_text("User type*")
    expect(page.locator('select[name="user_type"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_have_text("Create")


def test_create_user_validation_error(page: Page, demo_base_url: str):
    """Test that submitting an invalid form for User model shows an error message."""
    page.goto(f"{demo_base_url}/admin/user/create")
    page.locator('input[name="name"]').fill("")
    page.locator('button[type="submit"]').click()
    validation_error = page.locator('input[name="name"] ~ ul.text-red-500')
    expect(validation_error).to_be_visible()
    expect(validation_error).to_contain_text("String should have at least 1 character")


def test_create_user_successful_submission(debug_page: Page, demo_base_url: str):
    """Test that successful submission for User model redirects to the detail page."""
    page = debug_page
    page.goto(f"{demo_base_url}/admin/user/create")
    page.locator('input[name="name"]').fill("Test User")
    page.locator('input[name="email"]').fill("test@example.com")
    page.locator('input[name="is_active"]').check()
    page.locator('input[name="rating"]').fill("4.5")
    page.locator('select[name="user_type"]').select_option("ADMIN")
    page.locator('button[type="submit"]').click()
    page.screenshot(timeout=2000)
    # The redirect is handled by HTMX, so we need to wait for the URL to change.
    expect(page).to_have_url(re.compile(r".*/admin/user/\d+"))
    expect(page.get_by_role("heading", name=re.compile(r"User #"))).to_contain_text("User #")
    expect(page.locator("dd")).to_contain_text("Test User")
    expect(page.locator("dd")).to_contain_text("test@example.com")
    expect(page.locator("dd")).to_contain_text("True")
    expect(page.locator("dd")).to_contain_text("4.5")
    expect(page.locator("dd")).to_contain_text("admin")
