"""End-to-end tests for inline formset add/edit/delete rows (#334).

Uses the Country -> City inline configured in examples/simple/admin.py:
    CountryAdmin has inlines=[InlineModelSpec(model=City, fk_field="country_id", fields=["name"])]

The inline prefix is ``city`` (lowercase model name).
Seeded data: United Kingdom (London, Manchester), France (Paris).
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTRY_LIST = "/admin/country"
_COUNTRY_CREATE = "/admin/country/create"
_INLINE_PREFIX = "city"


def _navigate_to_first_country_edit(page: Page, base_url: str) -> None:
    """Go to the list and open the edit form for the first country row."""
    page.goto(base_url + _COUNTRY_LIST)
    page.get_by_test_id("list-row").first.get_by_test_id("row-edit-link").click()
    expect(page).to_have_url(re.compile(r"/edit$"))
    expect(page.get_by_test_id("model-form")).to_be_visible()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_inline_section_rendered_on_create(page: Page, demo_base_url: str) -> None:
    """Create form shows the inline formset section for Country -> City."""
    page.goto(demo_base_url + _COUNTRY_CREATE)

    expect(page.get_by_test_id("model-form")).to_be_visible()
    # The inline container must be present
    expect(page.get_by_test_id(f"inline-{_INLINE_PREFIX}")).to_be_visible()
    # The tbody that will hold rows
    expect(page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")).to_be_attached()
    # The "Add row" button
    expect(page.get_by_test_id(f"inline-{_INLINE_PREFIX}-add")).to_be_visible()


def test_add_row_appends_new_inline_row(page: Page, demo_base_url: str) -> None:
    """Clicking 'Add row' appends a new inline row to the tbody via HTMX."""
    page.goto(demo_base_url + _COUNTRY_CREATE)

    body = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")
    initial_rows = body.get_by_test_id(re.compile(rf"^inline-{_INLINE_PREFIX}-row-")).count()

    add_btn = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-add")
    add_btn.click()

    # Wait for HTMX to inject the new row
    page.wait_for_timeout(500)

    new_rows = body.get_by_test_id(re.compile(rf"^inline-{_INLINE_PREFIX}-row-")).count()
    assert new_rows == initial_rows + 1, (
        f"Expected {initial_rows + 1} inline rows after clicking Add, got {new_rows}"
    )


def test_submit_form_with_inline_rows_persists_data(page: Page, demo_base_url: str) -> None:
    """Filling inline fields and submitting the parent create form saves inline rows."""
    page.goto(demo_base_url + _COUNTRY_CREATE)

    # Fill the parent model field
    page.get_by_label("Name*").fill("Germany")

    # The spec has extra=1 so one empty row should already be present; fill it in
    body = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")
    first_row = body.get_by_test_id(f"inline-{_INLINE_PREFIX}-row-0")
    first_row.get_by_role("textbox", name=re.compile(r"name", re.IGNORECASE)).fill("Berlin")

    page.get_by_role("button", name="Create").click()

    # Should redirect to the detail view
    expect(page).to_have_url(re.compile(r"/admin/country/\d+$"))
    # The parent record name appears in the detail
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Germany")


def test_edit_form_shows_existing_inline_rows(page: Page, demo_base_url: str) -> None:
    """Edit view for a country pre-populates the inline tbody with its existing cities."""
    _navigate_to_first_country_edit(page, demo_base_url)

    body = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")
    # United Kingdom has London + Manchester seeded; at least one row should be present
    rows = body.get_by_test_id(re.compile(rf"^inline-{_INLINE_PREFIX}-row-"))
    row_count = rows.count()
    # Rows may include the extra empty trailing row from spec.extra=1
    assert row_count >= 1, "Expected at least one pre-populated inline row on the edit form"

    # First row should contain city data (non-empty name input)
    first_input = rows.first.get_by_role("textbox", name=re.compile(r"name", re.IGNORECASE))
    expect(first_input).not_to_be_empty()


def test_delete_checkbox_removes_inline_row_on_save(page: Page, demo_base_url: str) -> None:
    """Clicking Remove on an inline row and saving removes it from the persisted data."""
    _navigate_to_first_country_edit(page, demo_base_url)

    body = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")
    rows = body.get_by_test_id(re.compile(rf"^inline-{_INLINE_PREFIX}-row-"))
    initial_count = rows.count()
    assert initial_count >= 1, "Need at least one existing inline row to test deletion"

    # Click Remove on the first row (triggers JS to set DELETE=1 and hide the row)
    remove_btn = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-remove-0")
    remove_btn.click()

    # Row should be hidden by the JS onclick handler
    first_row = body.get_by_test_id(f"inline-{_INLINE_PREFIX}-row-0")
    expect(first_row).to_be_hidden()

    # Submit the form
    page.get_by_role("button", name="Update").click()

    # After save, edit form re-renders; the deleted city row should no longer appear
    expect(page).to_have_url(re.compile(r"/edit$"))
    expect(page.get_by_test_id("model-form")).to_be_visible()

    new_rows = (
        page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")
        .get_by_test_id(re.compile(rf"^inline-{_INLINE_PREFIX}-row-"))
        .count()
    )
    assert new_rows < initial_count, (
        f"Expected fewer rows after deletion ({new_rows} vs original {initial_count})"
    )


def test_inline_validation_errors_displayed(page: Page, demo_base_url: str) -> None:
    """Submitting a row with an invalid inline field shows per-field errors inline."""
    page.goto(demo_base_url + _COUNTRY_CREATE)

    # Fill parent model
    page.get_by_label("Name*").fill("TestCountry")

    # Ensure there is at least one inline row
    body = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-body")
    rows_before = body.get_by_test_id(re.compile(rf"^inline-{_INLINE_PREFIX}-row-")).count()
    if rows_before == 0:
        page.get_by_test_id(f"inline-{_INLINE_PREFIX}-add").click()
        page.wait_for_timeout(400)

    # Leave the name field empty to trigger a min_length validation error
    first_row = body.get_by_test_id(f"inline-{_INLINE_PREFIX}-row-0")
    name_input = first_row.get_by_role("textbox", name=re.compile(r"name", re.IGNORECASE))
    name_input.fill("")

    page.get_by_role("button", name="Create").click()

    # The form should re-render (not redirect) with inline error(s) visible
    expect(page.get_by_test_id("model-form")).to_be_visible()
    error_list = page.get_by_test_id(f"inline-{_INLINE_PREFIX}-0-name-errors")
    expect(error_list).to_be_visible()
