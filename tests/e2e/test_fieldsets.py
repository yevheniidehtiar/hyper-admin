"""E2E tests for fieldset grouping in create/update forms."""

import re

from playwright.sync_api import Page, expect


def test_create_form_renders_fieldsets(page: Page, demo_base_url: str) -> None:
    """Verify that the User create form renders configured fieldsets."""
    page.goto(f"{demo_base_url}/admin/user/create")

    # "Basic Info" fieldset should be visible (not collapsed)
    basic = page.get_by_test_id("fieldset-basic-info")
    expect(basic).to_be_visible()
    expect(basic).to_contain_text("Basic Info")

    # Fields inside Basic Info should be visible
    expect(page.get_by_label("Name")).to_be_visible()
    expect(page.get_by_label("Email")).to_be_visible()


def test_create_form_collapsed_fieldset(page: Page, demo_base_url: str) -> None:
    """Verify that a collapsed fieldset starts hidden and can be expanded."""
    page.goto(f"{demo_base_url}/admin/user/create")

    # "Settings" fieldset exists
    settings = page.get_by_test_id("fieldset-settings")
    expect(settings).to_be_visible()

    # The toggle button exists
    toggle = page.get_by_test_id("fieldset-toggle-settings")
    expect(toggle).to_be_visible()
    expect(toggle).to_contain_text("Settings")

    # Fields should be hidden initially (collapsed=True)
    is_active = page.locator('input[name="is_active"]')
    expect(is_active).to_be_hidden()

    # Click toggle to expand
    toggle.click()

    # Now fields should be visible
    expect(is_active).to_be_visible()


def test_fieldset_toggle_collapse(page: Page, demo_base_url: str) -> None:
    """Verify that clicking the toggle collapses an open fieldset."""
    page.goto(f"{demo_base_url}/admin/user/create")

    toggle = page.get_by_test_id("fieldset-toggle-basic-info")
    expect(toggle).to_be_visible()

    # Fields are visible initially
    name_input = page.get_by_label("Name")
    expect(name_input).to_be_visible()

    # Click to collapse
    toggle.click()

    # Fields should now be hidden
    expect(name_input).to_be_hidden()


def test_fieldset_description_visible(page: Page, demo_base_url: str) -> None:
    """Verify that fieldset description text is rendered."""
    page.goto(f"{demo_base_url}/admin/user/create")

    # Expand the Settings fieldset first
    toggle = page.get_by_test_id("fieldset-toggle-settings")
    toggle.click()

    # Description should be visible
    settings = page.get_by_test_id("fieldset-settings")
    expect(settings).to_contain_text("Advanced user settings")


def test_product_form_no_fieldsets(page: Page, demo_base_url: str) -> None:
    """Verify that Product (no fieldsets configured) renders fields without fieldset wrappers."""
    page.goto(f"{demo_base_url}/admin/product/create")

    # No fieldset elements should be present
    fieldsets = page.locator("fieldset.ha-fieldset")
    expect(fieldsets).to_have_count(0)

    # Fields should still render normally
    expect(page.get_by_label("Name")).to_be_visible()


def test_create_user_with_fieldsets_submits(page: Page, demo_base_url: str) -> None:
    """Verify that form submission works correctly with fieldsets."""
    page.goto(f"{demo_base_url}/admin/user/create")

    # Fill in Basic Info fields
    page.get_by_label("Name").fill("Fieldset Test User")
    page.get_by_label("Email").fill("fieldset@test.com")

    # Submit form
    page.get_by_role("button", name="Create").click()

    # Should redirect to detail page on success
    expect(page).to_have_url(re.compile(r".*/admin/user/\d+"))
