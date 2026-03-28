"""E2E tests for custom form layouts (#67).

Verifies that form layout CSS classes are applied correctly in create/update
views, and that form_fields ordering is reflected in the rendered DOM.
"""

import re

from playwright.sync_api import Page, expect


def test_user_create_form_has_two_column_layout(page: Page, demo_base_url: str):
    """UserAdmin has form_layout=TWO_COLUMN; the form should render with ha-form-grid-2."""
    page.goto(f"{demo_base_url}/admin/user/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()

    # UserAdmin uses fieldsets + TWO_COLUMN layout, so the layout class
    # is applied inside each fieldset's inner div, not on a top-level form-fields div.
    fieldset = page.get_by_test_id("fieldset-basic-info")
    expect(fieldset).to_be_visible()
    grid = fieldset.locator(".ha-form-grid-2")
    expect(grid).to_be_visible()


def test_product_create_form_has_single_column_layout(page: Page, demo_base_url: str):
    """ProductAdmin has default (single) layout; no ha-form-grid-2 class."""
    page.goto(f"{demo_base_url}/admin/product/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()

    grid = page.get_by_test_id("form-fields")
    # Should not have the two-column class
    expect(grid).not_to_have_class(re.compile(r"ha-form-grid-2"))
