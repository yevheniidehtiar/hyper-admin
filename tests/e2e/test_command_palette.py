"""Command palette E2E tests (st-v059-nav-04).

Spec: ``docs/specs/navigation-and-list-ux.md`` (Palette). Each test maps 1:1 to
a story scenario. Selectors follow CLAUDE.md: role, label, text, test id.

The app (``tests.e2e.apps.palette_app``) groups Invoices and Bills under
"Accounting" and Orders under "Sales"; ``alice`` is a superuser, ``bob`` may
view invoices but not add them, and ``carol`` may not view invoices.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import _spawn_uvicorn, _terminate


@pytest.fixture
def palette_base_url(e2e_port: int, tmp_path: Path) -> Iterator[str]:
    """Start :mod:`tests.e2e.apps.palette_app` on its own database file."""
    proc, base = _spawn_uvicorn(
        "tests.e2e.apps.palette_app",
        e2e_port,
        extra_env={"HYPERADMIN_E2E_PALETTE_DB": str(tmp_path / "palette.db")},
    )
    try:
        yield base
    finally:
        _terminate(proc)


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _result(page: Page, text: str):
    return page.get_by_test_id("palette-result").filter(has_text=text)


def test_the_palette_finds_a_model_by_group_name(page: Page, palette_base_url: str) -> None:
    """
    Scenario: the palette finds a model by group name
      Given "Accounting" contains Invoices and Bills
      When  the user presses Cmd+K and types "acco"
      Then  Invoices and Bills are listed and Enter on Invoices opens /admin/invoice
    """
    # Given "Accounting" contains Invoices and Bills (alice sees both, on the dashboard)
    _login(page, palette_base_url, "alice")

    # When the user presses Cmd+K and types "acco"
    page.keyboard.press("ControlOrMeta+k")
    expect(page.get_by_test_id("command-palette")).to_be_visible()
    page.get_by_test_id("palette-input").fill("acco")

    # Then Invoices and Bills are listed
    expect(page.get_by_test_id("palette-result")).to_have_count(2)
    expect(_result(page, "Bills")).to_be_visible()
    expect(_result(page, "Invoices")).to_be_visible()
    # And Enter on Invoices opens /admin/invoice
    page.keyboard.press("ArrowDown")
    expect(_result(page, "Invoices")).to_have_attribute("aria-selected", "true")
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{palette_base_url}/admin/invoice")


def test_the_palette_offers_new_only_where_allowed(page: Page, palette_base_url: str) -> None:
    """
    Scenario: the palette offers "New" only where allowed
      Given the user holds view_invoice but not add_invoice
      When  the user searches "invoice"
      Then  the Invoices result has no "New invoice" action
    """
    # Given the user holds view_invoice but not add_invoice
    _login(page, palette_base_url, "bob")

    # When the user searches "invoice"
    page.get_by_test_id("palette-trigger").click()
    page.get_by_test_id("palette-input").fill("invoice")

    # Then the Invoices result has no "New invoice" action
    expect(_result(page, "Invoices")).to_be_visible()
    expect(_result(page, "Invoices")).not_to_contain_text("New")


def test_the_palette_lists_recent_records(page: Page, palette_base_url: str) -> None:
    """
    Scenario: the palette lists recent records
      Given the user opened the edit page of order "ORD-1042"
      When  the user opens the palette with an empty query
      Then  "ORD-1042" is listed under Recent
    """
    # Given the user opened the edit page of order "ORD-1042"
    _login(page, palette_base_url, "alice")
    page.goto(f"{palette_base_url}/admin/order/1042/edit")
    expect(page.get_by_test_id("model-form")).to_be_visible()
    page.goto(f"{palette_base_url}/admin/")

    # When the user opens the palette with an empty query
    page.get_by_test_id("palette-trigger").click()

    # Then "ORD-1042" is listed under Recent
    recent = page.get_by_role("group", name="Recent")
    expect(recent.get_by_test_id("palette-result").filter(has_text="ORD-1042")).to_be_visible()


def test_forbidden_models_never_reach_the_page(page: Page, palette_base_url: str) -> None:
    """
    Scenario: forbidden models never reach the page
      Given the user lacks view_invoice
      When  any admin page renders
      Then  the ha-nav-data island contains no Invoices entry
    """
    # Given the user lacks view_invoice
    _login(page, palette_base_url, "carol")

    # When any admin page renders
    page.goto(f"{palette_base_url}/admin/order")

    # Then the ha-nav-data island contains no Invoices entry
    island = json.loads(page.evaluate("document.getElementById('ha-nav-data').textContent"))
    entries = [item for group in island["groups"] for item in group["items"]]
    assert {item["key"] for item in entries if item["kind"] == "model"} == {"bill", "order"}
    assert "Invoices" not in json.dumps(island)


def test_esc_closes_and_returns_focus(page: Page, palette_base_url: str) -> None:
    """
    Scenario: Esc closes and returns focus
      Given the palette was opened from the navbar trigger
      When  the user presses Esc
      Then  the dialog closes and focus is back on the trigger
    """
    # Given the palette was opened from the navbar trigger
    _login(page, palette_base_url, "alice")
    trigger = page.get_by_test_id("palette-trigger")
    trigger.click()
    expect(page.get_by_test_id("palette-input")).to_be_focused()

    # When the user presses Esc
    page.keyboard.press("Escape")

    # Then the dialog closes and focus is back on the trigger
    expect(page.get_by_test_id("command-palette")).to_be_hidden()
    expect(trigger).to_be_focused()


def test_records_of_opted_in_models_appear_in_the_palette(
    page: Page, palette_base_url: str
) -> None:
    """
    Scenario: records of opted-in models appear in the palette
      Given OrderAdmin(palette_search=True) and order "ORD-1042"
      When  the user types "1042" in the palette
      Then  "ORD-1042" is listed under Records, as an Orders record
      And   Enter opens its edit page
    """
    # Given OrderAdmin(palette_search=True) and order "ORD-1042"
    _login(page, palette_base_url, "alice")
    page.get_by_test_id("palette-trigger").click()

    # When the user types "1042" in the palette
    page.get_by_test_id("palette-input").fill("1042")

    # Then "ORD-1042" is listed under Records, as an Orders record
    records = page.get_by_role("group", name="Records")
    found = records.get_by_test_id("palette-result").filter(has_text="ORD-1042")
    expect(found).to_be_visible()
    expect(found).to_contain_text("Orders")

    # And Enter opens its edit page
    page.get_by_test_id("palette-input").press("Enter")
    expect(page).to_have_url(f"{palette_base_url}/admin/order/1042/edit")


def test_models_without_opt_in_are_never_queried(page: Page, palette_base_url: str) -> None:
    """
    Scenario: models without opt-in are never queried
      Given InvoiceAdmin without palette_search, and invoice "INV-1042"
      When  the user types "1042" in the palette
      Then  the record search answers for Orders only
      And   "INV-1042" is not listed
    """
    # Given InvoiceAdmin without palette_search, and invoice "INV-1042"
    _login(page, palette_base_url, "alice")
    page.get_by_test_id("palette-trigger").click()

    # When the user types "1042" in the palette
    with page.expect_response(lambda r: "/admin/nav/search" in r.url) as answer:
        page.get_by_test_id("palette-input").fill("1042")

    # Then the record search answers for Orders only
    assert [group["key"] for group in answer.value.json()["groups"]] == ["order"]
    expect(page.get_by_role("group", name="Records")).to_be_visible()

    # And "INV-1042" is not listed
    expect(_result(page, "INV-1042")).to_have_count(0)
