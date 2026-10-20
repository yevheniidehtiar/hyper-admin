"""End-to-end tests for FK relation select widget — preload and lazy modes (#183)."""

import re

from playwright.sync_api import Page, expect

# ---------------------------------------------------------------------------
# Country preload tests (Country has no FK → options baked into page)
# ---------------------------------------------------------------------------


def test_city_create_form_shows_country_relation_select(page: Page, demo_base_url: str) -> None:
    """City create form renders a relation select for the country_id FK field."""
    page.goto(demo_base_url + "/admin/city/create")

    expect(page.get_by_test_id("model-form")).to_be_visible()
    # The country_id FK renders as a combobox (select element)
    country_select = page.get_by_role("combobox", name=re.compile(r"country", re.IGNORECASE))
    expect(country_select).to_be_visible()


def test_city_create_form_preloaded_country_options_present(page: Page, demo_base_url: str) -> None:
    """In preload mode the country options are present in the HTML before any interaction."""
    page.goto(demo_base_url + "/admin/city/create")

    country_select = page.get_by_role("combobox", name=re.compile(r"country", re.IGNORECASE))
    expect(country_select).to_be_visible()

    # Options must be present without any JS interaction (preload baked in)
    options = country_select.locator("option")
    # At minimum the blank option + UK + France from seed data
    expect(options).to_have_count(3, timeout=3000)
    option_texts = country_select.inner_text()
    assert "United Kingdom" in option_texts
    assert "France" in option_texts


def test_city_create_form_submit_redirects_to_detail(page: Page, demo_base_url: str) -> None:
    """Submitting the create form with a selected country redirects to the city detail page."""
    page.goto(demo_base_url + "/admin/city/create")

    page.get_by_label("Name").fill("Bristol")

    country_select = page.get_by_role("combobox", name=re.compile(r"country", re.IGNORECASE))
    # Select United Kingdom
    country_select.select_option(label="United Kingdom")

    page.get_by_role("button", name="Create").click()

    expect(page).to_have_url(re.compile(r"/admin/city/\d+$"))
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Bristol")


def test_city_update_form_preselects_current_country(page: Page, demo_base_url: str) -> None:
    """Updating a city shows the current country preselected in the relation select."""
    # Navigate to city list and click edit on the first row (London → UK)
    page.goto(demo_base_url + "/admin/city")

    page.get_by_test_id("list-row").first.get_by_test_id("row-edit-link").click()
    expect(page).to_have_url(re.compile(r"/edit$"))
    expect(page.get_by_test_id("model-form")).to_be_visible()

    country_select = page.get_by_role("combobox", name=re.compile(r"country", re.IGNORECASE))
    # The currently selected option should be non-empty (UK for London)
    selected = country_select.evaluate("el => el.options[el.selectedIndex].text")
    assert selected != "---------"


def test_country_list_shows_entries(page: Page, demo_base_url: str) -> None:
    """Country list view shows seeded countries."""
    page.goto(demo_base_url + "/admin/country")

    expect(page.get_by_test_id("list-table")).to_be_visible()
    expect(page.get_by_test_id("list-table")).to_contain_text("United Kingdom")
    expect(page.get_by_test_id("list-table")).to_contain_text("France")


def test_city_list_shows_entries(page: Page, demo_base_url: str) -> None:
    """City list view shows seeded cities."""
    page.goto(demo_base_url + "/admin/city")

    expect(page.get_by_test_id("list-table")).to_be_visible()
    expect(page.get_by_test_id("list-table")).to_contain_text("London")
    expect(page.get_by_test_id("list-table")).to_contain_text("Paris")


def test_city_create_popup_creates_and_selects_country(page: Page, demo_base_url: str) -> None:
    """Scenario: "+" popup creates the related row and selects it."""
    # Given the City create form, whose country_id FK targets the registered Country admin
    page.goto(demo_base_url + "/admin/city/create")
    expect(page.get_by_test_id("autocomplete-country_id")).to_be_visible()

    # When the user opens the "+" popup and saves a new country
    page.get_by_test_id("autocomplete-add-country_id").click()
    popup = page.get_by_test_id("popup-form")
    expect(popup).to_be_visible()
    popup.get_by_label("Name").fill("Portugal")
    page.get_by_test_id("popup-form-submit").click()

    # Then the popup closes and the parent field selects the new country
    expect(page.get_by_test_id("popup-form")).to_have_count(0)
    expect(page.get_by_test_id("popup-root")).to_be_hidden()
    country_select = page.get_by_test_id("autocomplete-select-country_id")
    selected = country_select.evaluate("el => el.options[el.selectedIndex].text")
    assert selected == "Portugal"


def test_city_autocomplete_search_filters_options(page: Page, demo_base_url: str) -> None:
    """Scenario: typing in the search input swaps in the matching options."""
    # Given the City create form
    page.goto(demo_base_url + "/admin/city/create")

    # When the user types part of a country name
    page.get_by_test_id("autocomplete-country_id").fill("fra")

    # Then only the matching country is offered
    options = page.get_by_test_id("autocomplete-select-country_id").locator("option")
    expect(options).to_have_count(1)
    expect(options.first).to_have_text("France")
