"""End-to-end tests for the HTMX FK autocomplete widget (H6, v0.5.5).

Spec: ``docs/specs/htmx-autocomplete.md`` — one test per BDD scenario, named
after it. Design: ``docs/design/system/components/AutocompleteStates``.
Inline ``# Given / # When / # Then`` comments are mandatory (BDD conventions).

Selectors follow ``CLAUDE.md`` (E2E Selector Convention):
``get_by_role`` > ``get_by_label`` > ``get_by_text`` > ``get_by_test_id``.
``ha-*`` CSS classes are styling-only and never used as selectors. The widget's
own ids are ``autocomplete-{field}`` (search input), ``autocomplete-select-{field}``
(value select), ``autocomplete-add-{field}`` ("+") and ``popup-root``.

The companion app (``tests.e2e.apps.autocomplete``) registers Supplier, Variant
and Product (not Brand), seeds suppliers 42 "Acme" (Paris), 43 "Acme Packaging"
(Lyon) and 44 "Brabant Bakkerij" (Tilburg), variants 1 "Blue" (supplier 42) and
2 "Red" (supplier 43), and signs the superuser ``alice`` in.
"""

from __future__ import annotations

from http import HTTPStatus

from playwright.sync_api import Locator, Page, Request, expect

PRODUCT_CREATE = "/admin/product/create"
SUPPLIER_CHOICES = "/admin/product/choices/supplier"
VARIANT_CHOICES = "/admin/product/choices/variant"


def _login(page: Page, base_url: str) -> None:
    """Sign in as the superuser and land on the dashboard."""
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _open_create_form(page: Page, base_url: str) -> None:
    _login(page, base_url)
    page.goto(base_url + PRODUCT_CREATE)
    expect(page.get_by_test_id("model-form")).to_be_visible()


def _option_labels(select: Locator) -> list[str]:
    """Visible labels of a select's options, in order (options have no Playwright role)."""
    return select.locator("option").evaluate_all("options => options.map(o => o.textContent)")


def _is_choices_request(path: str, *params: str):
    """Predicate for ``expect_request``: a GET of ``path`` whose query carries every param."""

    def matches(request: Request) -> bool:
        return (
            request.method == "GET"
            and path in request.url
            and all(param in request.url for param in params)
        )

    return matches


def test_fk_field_renders_autocomplete_widget_by_default(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: FK field renders an autocomplete widget by default
      Given a ModelAdmin for Product with FK to Supplier
      When  the user opens /admin/products/create
      Then  the Supplier field renders as <input type="search"> with hx-get="/admin/products/choices/supplier_id"
      And   typing "ac" issues a debounced GET /admin/products/choices/supplier_id?q=ac
    """
    # Given the Product admin, whose supplier_id FK targets the registered Supplier
    # When the user opens the create form
    _open_create_form(page, autocomplete_base_url)

    # Then the Supplier field is a search input that GETs the relation's choices endpoint
    search = page.get_by_test_id("autocomplete-supplier_id")
    expect(search).to_be_visible()
    expect(search).to_have_attribute("type", "search")
    expect(search).to_have_attribute("hx-get", autocomplete_base_url + SUPPLIER_CHOICES)
    expect(search).to_have_attribute("placeholder", "Search supplier")
    # And the native select carries the value, preloaded with the seeded suppliers
    select = page.get_by_test_id("autocomplete-select-supplier_id")
    expect(select).to_have_value("")
    assert _option_labels(select) == ["---------", "Acme", "Acme Packaging", "Brabant Bakkerij"]

    # And typing "ac" issues one debounced GET with q=ac
    with page.expect_request(_is_choices_request(SUPPLIER_CHOICES, "q=ac")) as request_info:
        search.fill("ac")
    assert request_info.value.method == "GET"
    expect(select.locator("option")).to_have_count(2)


def test_dependent_fk_forwards_parent_via_hx_include(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: dependent FK forwards the parent value via hx-include
      Given AdminOptions(relation_filters={"variant_id": {"depends_on": "supplier_id"}})
      When  the user selects supplier_id=42 and focuses the variant_id field
      Then  the variant_id widget's hx-get includes "?supplier_id=42"
      And   the dropdown lists only variants whose supplier_id == 42
    """
    # Given the create form, where variant_id depends on supplier_id
    _open_create_form(page, autocomplete_base_url)
    variant_search = page.get_by_test_id("autocomplete-variant_id")
    expect(variant_search).to_have_attribute("hx-include", "[name='supplier_id']")

    # When the user selects supplier 42
    with page.expect_request(
        _is_choices_request(VARIANT_CHOICES, "supplier_id=42")
    ) as request_info:
        page.get_by_test_id("autocomplete-select-supplier_id").select_option("42")

    # Then the variant choices request carries the parent value
    assert "supplier_id=42" in request_info.value.url
    # And the variant field is usable and lists only supplier 42's variants
    expect(variant_search).to_be_enabled()
    variant_select = page.get_by_test_id("autocomplete-select-variant_id")
    expect(variant_select).to_be_enabled()
    expect(variant_select.locator("option")).to_have_count(1)
    assert _option_labels(variant_select) == ["Blue"]
    # And the field says why it changed
    expect(page.get_by_text("Cleared because the supplier changed.")).to_be_visible()


def test_dependent_fk_with_no_parent_lists_nothing(page: Page, autocomplete_base_url: str) -> None:
    """
    Scenario: dependent FK with no parent value lists nothing
      Given the same dependent wiring
      When  the user focuses variant_id before choosing a supplier
      Then  the dropdown renders an empty <option> list
      And   the field shows placeholder "Pick a supplier first"
    """
    # Given the create form with no supplier chosen
    _open_create_form(page, autocomplete_base_url)
    expect(page.get_by_test_id("autocomplete-select-supplier_id")).to_have_value("")

    # When the user reaches the variant field before choosing a supplier
    variant_search = page.get_by_test_id("autocomplete-variant_id")
    variant_select = page.get_by_test_id("autocomplete-select-variant_id")

    # Then the field waits: nothing to pick but the blank option
    expect(variant_select.locator("option")).to_have_count(1)
    expect(variant_select.locator("option").first).to_have_attribute("value", "")
    expect(variant_select).to_be_disabled()
    # And it shows the configured placeholder and explains what to do
    expect(variant_search).to_have_attribute("placeholder", "Pick a supplier first")
    expect(variant_search).to_be_disabled()
    expect(page.get_by_text("Pick the supplier above to list its variant options.")).to_be_visible()
    # And the "+" for a variant waits too
    expect(page.get_by_role("button", name="Add variant")).to_be_disabled()


def test_popup_creates_related_row_and_selects_it(page: Page, autocomplete_base_url: str) -> None:
    """
    Scenario: "+" popup creates the related row and selects it
      Given the Supplier model is registered in the same Admin
      When  the user clicks "+" next to the supplier_id field on /admin/products/create
      Then  a modal loads /admin/suppliers/create-popup
      And   on save the modal closes
      And   the parent supplier_id field has the new supplier's id and label
    """
    # Given the create form, whose supplier_id FK targets the registered Supplier
    _open_create_form(page, autocomplete_base_url)
    expect(page.get_by_test_id("popup-root")).to_be_hidden()

    # When the user clicks "+" next to the supplier field
    with page.expect_request("**/admin/supplier/create-popup?target=supplier_id"):
        page.get_by_role("button", name="Add supplier").click()

    # Then the create popup opens as a dialog
    dialog = page.get_by_role("dialog", name="Add supplier")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("Saving selects it in the supplier field.")).to_be_visible()
    popup = page.get_by_test_id("popup-form")
    popup.get_by_label("Name").fill("Zed Corp")
    popup.get_by_label("City").fill("Utrecht")

    # When the user saves
    with page.expect_response("**/admin/supplier/create-popup") as response_info:
        popup.get_by_role("button", name="Save and select").click()
    assert response_info.value.status == HTTPStatus.OK

    # Then the modal closes
    expect(page.get_by_test_id("popup-form")).to_have_count(0)
    expect(page.get_by_test_id("popup-root")).to_be_hidden()
    # And the supplier field holds the new supplier's id and label
    select = page.get_by_test_id("autocomplete-select-supplier_id")
    new_id = select.input_value()
    assert new_id not in ("", "42", "43", "44")
    assert int(new_id) > 44
    selected_label = select.evaluate("el => el.options[el.selectedIndex].text")
    assert "Zed Corp" in selected_label


def test_popup_hidden_when_related_model_unregistered(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: "+" popup is hidden when the related model is not registered
      Given Supplier is not registered with this Admin
      When  the user opens /admin/products/create
      Then  the Supplier field has no "+" button
    """
    # Given Brand is not registered with this Admin (Supplier is, for the other scenarios)
    # When the user opens the create form
    _open_create_form(page, autocomplete_base_url)

    # Then the Brand field renders as an autocomplete without a "+" button
    expect(page.get_by_test_id("autocomplete-brand_id")).to_be_visible()
    expect(page.get_by_test_id("autocomplete-add-brand_id")).to_have_count(0)
    expect(page.get_by_role("button", name="Add brand")).to_have_count(0)
    # And a registered target keeps its "+"
    expect(page.get_by_role("button", name="Add supplier")).to_be_visible()


def test_display_template_renders_custom_option_rows(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: display_template renders custom option rows
      Given AdminOptions(relation_display={"supplier_id": "{name} — {city}"})
      When  the user types "ac" in the supplier_id widget
      Then  each <option> label is rendered as "{name} — {city}" for the matching row
    """
    # Given the create form, whose supplier options use "{name} — {city}"
    _open_create_form(page, autocomplete_base_url)

    # When the user types "ac" in the supplier widget
    with page.expect_response(
        lambda r: SUPPLIER_CHOICES in r.url and "q=ac" in r.url
    ) as response_info:
        page.get_by_test_id("autocomplete-supplier_id").fill("ac")
    assert response_info.value.status == HTTPStatus.OK

    # Then each matching row is rendered with the display template
    select = page.get_by_test_id("autocomplete-select-supplier_id")
    expect(select.locator("option")).to_have_count(2)
    assert _option_labels(select) == ["Acme — Paris", "Acme Packaging — Lyon"]
    # And the clear button appears now that the input has text
    expect(page.get_by_role("button", name="Clear supplier")).to_be_visible()


def test_choices_view_rejects_unknown_relation_field(
    page: Page, autocomplete_base_url: str
) -> None:
    """
    Scenario: choices_view rejects unknown relation field
      When  GET /admin/products/choices/not_a_field is called
      Then  the response is 404 with detail "Unknown relation field: 'not_a_field'"
    """
    # Given a signed-in session (page.request shares the browser's cookies)
    _login(page, autocomplete_base_url)

    # When the choices endpoint is called for a field that is not a relation
    response = page.request.get(f"{autocomplete_base_url}/admin/product/choices/not_a_field")

    # Then it is refused with a 404 that names the field
    assert response.status == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "Unknown relation field: 'not_a_field'"
