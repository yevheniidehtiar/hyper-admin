"""E2E: the autocomplete options list starts right at its field, with no gap.

One test per scenario, against the autocomplete fixture app
(``tests.e2e.apps.autocomplete``, superuser ``alice``/``secret123``):

* the single-value options list opens flush under its field
* the single-value options list flips flush above its field near the viewport bottom
* the multi-value options list hangs flush under its search field

"At the field" means within 2px of its edge: the borders may overlap, they may not part.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from playwright.sync_api import Locator

FLUSH = 2


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _box(locator: Locator) -> dict[str, float]:
    box = locator.bounding_box()
    assert box is not None
    return box


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_single_value_options_list_opens_flush_under_its_field(
    page: Page, autocomplete_base_url: str, theme: str
) -> None:
    """
    Scenario: the single-value options list opens flush under its field
      Given the invoice edit form with its Customer combobox, in light or dark mode
      When  the user clicks Customer
      Then  the options list starts at the field's bottom edge, within 2px
    """
    # Given the invoice edit form with its Customer combobox, in light or dark mode
    page.emulate_media(color_scheme=theme)
    _login(page, autocomplete_base_url)
    page.goto(autocomplete_base_url + "/admin/invoice/1/edit")
    customer = page.get_by_role("combobox", name="Customer")

    # When the user clicks Customer
    customer.click()
    expect(customer).to_have_attribute("aria-expanded", "true")

    # Then the options list starts at the field's bottom edge, within 2px
    field = _box(customer)
    options = _box(page.get_by_role("listbox", name="Customer"))
    assert options["y"] == pytest.approx(field["y"] + field["height"], abs=FLUSH)


def test_the_single_value_options_list_flips_flush_above_its_field_near_the_viewport_bottom(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: the single-value options list flips flush above its field near the viewport bottom
      Given the invoice edit form scrolled so Customer sits at the bottom of a short window
      When  the user focuses Customer
      Then  the options list ends at the field's top edge, within 2px
    """
    # Given the invoice edit form scrolled so Customer sits at the bottom of a short window
    page.set_viewport_size({"width": 1280, "height": 600})
    _login(page, autocomplete_base_url)
    page.goto(autocomplete_base_url + "/admin/invoice/1/edit")
    customer = page.get_by_role("combobox", name="Customer")
    customer.evaluate(
        """(input) => {
            const gap = window.innerHeight - input.getBoundingClientRect().bottom - 40;
            document.body.style.paddingBlockStart = Math.max(0, gap) + 'px';
        }"""
    )
    field = _box(customer)
    assert field["y"] + field["height"] > 600 - 60

    # When the user focuses Customer
    # (focus: a pointer click would first scroll the field clear of the sticky form actions)
    customer.focus()
    expect(customer).to_have_attribute("aria-expanded", "true")

    # Then the options list ends at the field's top edge, within 2px
    field = _box(customer)
    options = _box(page.get_by_role("listbox", name="Customer"))
    assert options["y"] + options["height"] == pytest.approx(field["y"], abs=FLUSH)


def test_the_multi_value_options_list_hangs_flush_under_its_search_field(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: the multi-value options list hangs flush under its search field
      Given a form with a multi-value Contacts autocomplete
      When  the page renders
      Then  the Contacts options list starts at the search field's bottom edge, within 2px
    """
    # Given a form with a multi-value Contacts autocomplete
    _login(page, autocomplete_base_url)

    # When the page renders
    page.goto(autocomplete_base_url + "/admin/e2e/multi-widget")

    # Then the Contacts options list starts at the search field's bottom edge, within 2px
    search = _box(page.get_by_test_id("autocomplete-contacts"))
    options = _box(page.get_by_role("listbox", name="Contacts"))
    assert options["y"] == pytest.approx(search["y"] + search["height"], abs=FLUSH)
