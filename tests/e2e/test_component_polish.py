"""E2E: component polish found in the UI/UX review of the ERP demo.

One test per scenario, against the ERP demo app (``examples.erp.main``,
superuser ``admin``/``admin``):

* a validation error keeps the customer autocomplete working
* the folded filter panel opens under its button, not below the list
* the command palette's search icon sits inside its field
* every leading search icon sits the same distance from its field's edge
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Locator


@pytest.fixture
def erp_url(start_server: Callable[..., str]) -> str:
    """Start the ERP demo app and return its base URL."""
    return start_server("examples.erp.main", ready_path="/")


def _login(page: Page, base_url: str) -> None:
    page.goto(base_url + "/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base_url + "/admin/")


def _icon_inset(field: Locator) -> float:
    """Distance from a field's start edge to the leading icon drawn over it."""
    return field.evaluate(
        """(input) => {
            const box = input.getBoundingClientRect();
            let node = input;
            while (node && !node.querySelector('svg')) node = node.parentElement;
            const icon = node.querySelector('svg').getBoundingClientRect();
            return icon.left - box.left;
        }"""
    )


def test_a_validation_error_keeps_the_customer_autocomplete_working(
    page: Page, erp_url: str
) -> None:
    """
    Scenario: a validation error keeps the customer autocomplete working
      Given the invoice create form with every field empty
      When  the user clicks Create and the server answers 422
      Then  Customer is still one combobox, not a combobox plus a raw select
      And   typing in it opens the list of matching customers
    """
    # Given the invoice create form with every field empty
    _login(page, erp_url)
    page.goto(erp_url + "/admin/invoice/create")

    # When the user clicks Create and the server answers 422
    with page.expect_response(lambda r: r.request.method == "POST") as answer:
        page.get_by_role("button", name="Create", exact=True).click()
    assert answer.value.status == 422
    expect(page.get_by_test_id("error-summary")).to_be_visible()

    # Then Customer is still one combobox, not a combobox plus a raw select
    customer = page.get_by_role("combobox", name="Customer")
    expect(customer).to_be_visible()
    expect(page.get_by_test_id("autocomplete-select-customer_id")).to_have_attribute(
        "role", "listbox"
    )

    # And typing in it opens the list of matching customers
    with page.expect_response(lambda r: "choices" in r.url or "autocomplete" in r.url):
        customer.fill("a")
    expect(customer).to_have_attribute("aria-expanded", "true")


def test_the_filter_panel_opens_under_its_button_on_a_phone(page: Page, erp_url: str) -> None:
    """
    Scenario: the filter panel opens under its button on a phone
      Given the invoice list on a 393px wide phone, filters folded into a button
      When  the user taps Filters
      Then  the filter panel shows above the first invoice, right under the button
    """
    # Given the invoice list on a 393px wide phone, filters folded into a button
    page.set_viewport_size({"width": 393, "height": 852})
    _login(page, erp_url)
    page.goto(erp_url + "/admin/invoice")
    panel = page.get_by_test_id("filter-sidebar")
    expect(panel).to_be_hidden()

    # When the user taps Filters
    button = page.get_by_role("button", name="Filters", exact=True)
    button.click()

    # Then the filter panel shows above the first invoice, right under the button
    expect(panel).to_be_visible()
    panel_box = panel.bounding_box()
    button_box = button.bounding_box()
    row_box = page.get_by_test_id("list-row").first.bounding_box()
    assert panel_box and button_box and row_box
    assert button_box["y"] < panel_box["y"] < row_box["y"]


def test_the_palette_search_icon_sits_inside_its_field(page: Page, erp_url: str) -> None:
    """
    Scenario: the palette search icon sits inside its field
      Given the invoice list on a laptop
      When  the user opens the command palette
      Then  the search icon sits 12px inside the input, clear of its border
    """
    # Given the invoice list on a laptop
    page.set_viewport_size({"width": 1280, "height": 800})
    _login(page, erp_url)
    page.goto(erp_url + "/admin/invoice")

    # When the user opens the command palette
    page.get_by_test_id("palette-trigger").click()
    palette_input = page.get_by_test_id("palette-input")
    expect(palette_input).to_be_visible()

    # Then the search icon sits 12px inside the input, clear of its border
    assert _icon_inset(palette_input) == pytest.approx(12, abs=1)


def test_every_search_icon_sits_the_same_distance_from_its_field_edge(
    page: Page, erp_url: str
) -> None:
    """
    Scenario: every search icon sits the same distance from its field edge
      Given the invoice list and the invoice edit form on a laptop
      When  the navbar search, list search, filter search and customer autocomplete render
      Then  each leading search icon starts 12px from its field's edge
    """
    # Given the invoice list and the invoice edit form on a laptop
    page.set_viewport_size({"width": 1440, "height": 900})
    _login(page, erp_url)

    # When the navbar search, list search, filter search and customer autocomplete render
    page.goto(erp_url + "/admin/invoice")
    fields = [
        page.get_by_test_id("palette-trigger"),
        page.get_by_test_id("search-input"),
        page.get_by_test_id("filter-customer_id-search"),
    ]
    insets = [_icon_inset(field) for field in fields]
    page.goto(erp_url + "/admin/invoice/1/edit")
    insets.append(_icon_inset(page.get_by_role("combobox", name="Customer")))

    # Then each leading search icon starts 12px from its field's edge
    assert insets == pytest.approx([12, 12, 12, 12], abs=1)
