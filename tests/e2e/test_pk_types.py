"""End-to-end tests for non-int primary keys (BYOA SDD, BDD scenarios: Keys).

Runs against the dedicated fixture app :mod:`tests.e2e.apps.pk_types`, which
registers a UUID-keyed ``Document`` (``list_editable = ["title"]``), a
natural ``str``-keyed ``Country`` and an int-keyed ``Product``. One test per
scenario of story ``st-v058-byoa-49``; locators are role, label, text and
test-id only.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

_UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _row_pk(page: Page, text: str) -> str:
    """Return the primary key of the list row showing ``text``, read from its View link."""
    row = page.get_by_test_id("list-row").filter(has_text=text)
    href = row.get_by_test_id("row-view-link").get_attribute("href") or ""
    return href.rstrip("/").rsplit("/", 1)[-1]


def test_uuid_crud(page: Page, pk_types_base_url: str) -> None:
    """
    Scenario: UUID CRUD
      Given a UUID model
      When  the user views, edits and deletes a row via row-view-link, row-edit-link,
            row-delete-btn
      Then  each step succeeds
    """
    # Given a UUID model (Document) with a seeded row "Alpha"
    page.goto(pk_types_base_url + "/admin/document")
    alpha = page.get_by_test_id("list-row").filter(has_text="Alpha")
    pk = _row_pk(page, "Alpha")
    assert re.fullmatch(_UUID_RE, pk)

    # When the user views the row via row-view-link
    alpha.get_by_test_id("row-view-link").click()

    # Then the detail page for that UUID opens
    expect(page).to_have_url(re.compile(rf"/admin/document/{pk}$"))
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Alpha")

    # When the user edits the row via row-edit-link
    page.goto(pk_types_base_url + "/admin/document")
    page.get_by_test_id("list-row").filter(has_text="Alpha").get_by_test_id("row-edit-link").click()
    expect(page).to_have_url(re.compile(rf"/admin/document/{pk}/edit$"))
    page.get_by_label("Title").fill("Alpha edited")
    page.get_by_role("button", name="Update").click()

    # Then the list shows the new title under the same UUID
    expect(page).to_have_url(re.compile(r"/admin/document$"))
    expect(page.get_by_test_id("list-table")).to_contain_text("Alpha edited")
    assert _row_pk(page, "Alpha edited") == pk
    # And no extra row was created
    expect(page.get_by_test_id("list-row")).to_have_count(2)

    # When the user deletes the row via row-delete-btn
    page.on("dialog", lambda d: d.accept())
    page.get_by_test_id("list-row").filter(has_text="Alpha edited").get_by_test_id(
        "row-delete-btn"
    ).click()

    # Then the row is gone from the list
    expect(page.get_by_test_id("list-row")).to_have_count(1)
    expect(page.get_by_test_id("list-table")).not_to_contain_text("Alpha edited")
    # And its detail page now returns 404
    response = page.goto(f"{pk_types_base_url}/admin/document/{pk}")
    assert response is not None
    assert response.status == 404


def test_malformed_uuid(page: Page, pk_types_base_url: str) -> None:
    """
    Scenario: malformed UUID
      Given the fixture app
      When  GET /admin/document/not-a-uuid is requested
      Then  the status is 404
    """
    # Given the fixture app (Document has a UUID primary key)

    # When GET /admin/document/not-a-uuid is requested
    response = page.goto(pk_types_base_url + "/admin/document/not-a-uuid")

    # Then the status is 404
    assert response is not None
    assert response.status == 404


def test_natural_key_create(page: Page, pk_types_base_url: str) -> None:
    """
    Scenario: natural key create
      Given a str-pk model
      When  the user creates code 'NL'
      Then  the detail page for NL opens
    """
    # Given a str-pk model (Country.code has no default, so it is editable on create)
    page.goto(pk_types_base_url + "/admin/country/create")
    expect(page.get_by_label("Code")).to_be_visible()

    # When the user creates code 'NL'
    page.get_by_label("Code").fill("NL")
    page.get_by_label("Name").fill("Netherlands")
    page.get_by_role("button", name="Create").click()

    # Then the detail page for NL opens
    expect(page).to_have_url(re.compile(r"/admin/country/NL$"))
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Netherlands")


def test_uuid_inline_edit(page: Page, pk_types_base_url: str) -> None:
    """
    Scenario: UUID inline edit
      Given list_editable on the UUID model
      When  the user inline-edits a cell
      Then  the cell-saved flag appears
    """
    # Given list_editable = ["title"] on the UUID-keyed Document
    page.goto(pk_types_base_url + "/admin/document")
    pk = _row_pk(page, "Beta")

    # When the user inline-edits Beta's title cell
    page.get_by_test_id(f"cell-edit-title-{pk}").click()
    expect(page.get_by_test_id(f"cell-editor-title-{pk}")).to_be_visible()
    page.get_by_role("textbox", name="Title", exact=True).fill("Beta inline")
    page.get_by_test_id(f"cell-save-title-{pk}").click()

    # Then the cell shows the new title
    expect(page.get_by_test_id(f"cell-value-title-{pk}")).to_have_text("Beta inline")
    # And the cell-saved flag appears
    expect(page.get_by_test_id(f"cell-saved-flag-title-{pk}")).to_be_attached()


def test_int_pk_keeps_numeric_urls(page: Page, pk_types_base_url: str) -> None:
    """
    Scenario: int primary key keeps numeric item URLs
      Given an int-pk model with one seeded row
      When  the user opens its list page and clicks the row's View link
      Then  the detail URL ends in the numeric id
    """
    # Given an int-pk model (Product) with one seeded row
    page.goto(pk_types_base_url + "/admin/product")

    # When the user clicks the row's View link
    page.get_by_test_id("list-row").filter(has_text="Widget").get_by_test_id(
        "row-view-link"
    ).click()

    # Then the detail URL ends in the numeric id
    expect(page).to_have_url(re.compile(r"/admin/product/\d+$"))
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Widget")
