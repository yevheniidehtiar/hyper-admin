import re

import pytest
from playwright.sync_api import Page, expect


def test_create_view_form_rendering(page: Page, demo_base_url: str):
    """Test that the create form is rendered correctly."""
    page.goto(f"{demo_base_url}/admin/testproduct/create")
    expect(page).to_have_title("HyperAdmin")
    h2 = page.locator("h2")
    expect(h2).to_be_visible()
    expect(h2).to_have_text("Create TestProduct")
    expect(page.locator(f'form[hx-post="{demo_base_url}/admin/testproduct"]')).to_be_visible()
    expect(page.locator('label[for="name"]')).to_have_text("Name")
    expect(page.locator('input[name="name"]')).to_be_visible()
    expect(page.locator('label[for="description"]')).to_have_text("Description")
    expect(page.locator('textarea[name="description"]')).to_be_visible()
    expect(page.locator('label[for="price"]')).to_have_text("Price")
    expect(page.locator('input[name="price"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_have_text("Create")


def test_create_view_validation_error(page: Page, demo_base_url: str):
    """Test that submitting an invalid form shows an error message."""
    page.goto(f"{demo_base_url}/admin/testproduct/create")
    page.locator('button[type="submit"]').click()
    expect(page.locator(".text-red-500")).to_be_visible()
    expect(page.locator(".text-red-500")).to_contain_text("Field required")


def test_create_view_successful_submission(page: Page, demo_base_url: str):
    """Test that successful submission redirects to the detail page."""
    page.goto(f"{demo_base_url}/admin/testproduct/create")
    page.locator('input[name="name"]').fill("E2E Test Product")
    page.locator('textarea[name="description"]').fill("A product created from an E2E test.")
    page.locator('input[name="price"]').fill("123.45")
    page.locator('button[type="submit"]').click()

    # The redirect is handled by HTMX, so we need to wait for the URL to change.
    expect(page).to_have_url(re.compile(r".*/admin/testproduct/\d+"))
    expect(page.locator("h2")).to_contain_text("TestProduct #")
    expect(page.locator("dd")).to_contain_text("E2E Test Product")
