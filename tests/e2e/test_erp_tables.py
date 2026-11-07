"""E2E: ERP showcase tables, figures and report (ep-ux-erp-01, tables lane).

One test per story scenario, against the ERP demo app (``examples.erp.main``,
seeded with Faker data, superuser ``admin``/``admin``):

* st-ux-erp-04  money formatting and blank zero side of a journal line
* st-ux-erp-13  status pills with an overdue variant
* st-ux-erp-14  phone cards with a hierarchy
* st-ux-erp-08  wide lists on a tablet
* st-ux-erp-17  one name for the P&L report, readable totals on a phone
* st-ux-erp-20  invoice filters and a bulk "Mark paid" action
* st-ux-erp-19  dashboard figures linking to filtered lists
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

MONEY = re.compile(r"^\d{1,3}(,\d{3})*\.\d{2}$")


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


def _open(page: Page, base_url: str, path: str) -> None:
    _login(page, base_url)
    page.goto(base_url + path)
    expect(page.get_by_test_id("list-table")).to_be_visible()


def test_amounts_are_formatted(page: Page, erp_url: str) -> None:
    """
    Scenario: amounts are formatted
      Given an invoice with a total such as 3013.3 in locale en
      When  the invoice list is shown
      Then  the total reads with two decimals and grouping and is right-aligned
    """
    # Given the seeded invoices
    # When the invoice list is shown
    _open(page, erp_url, "/admin/invoice")

    # Then every total is formatted and right-aligned
    totals = page.get_by_test_id("list-row").first.get_by_role("cell").nth(-2)
    for row in page.get_by_test_id("list-row").all():
        text = row.get_by_role("cell").nth(-2).inner_text().strip()
        assert MONEY.match(text), text
    align = totals.evaluate("el => getComputedStyle(el).textAlign")
    assert align in {"end", "right"}


def test_zero_side_of_a_journal_line_is_blank(page: Page, erp_url: str) -> None:
    """
    Scenario: zero side of a journal line is blank
      Given journal lines that carry a debit or a credit
      Then  the empty side's cell is empty, never 0.0
    """
    # Given the seeded journal lines
    # When the journal line list is shown
    _open(page, erp_url, "/admin/journalline")

    # Then each row has one filled and one empty money cell
    for row in page.get_by_test_id("list-row").all():
        cells = row.get_by_role("cell")
        debit = cells.nth(-3).inner_text().strip()
        credit = cells.nth(-2).inner_text().strip()
        assert "0.0" not in (debit, credit)
        assert (debit == "") != (credit == ""), (debit, credit)


def test_status_is_shown_as_a_pill(page: Page, erp_url: str) -> None:
    """
    Scenario: status is shown as a pill
      Given invoices with status Paid
      Then  the status cell is a pill with the success tone and the text "Paid"
    """
    # Given the invoice list filtered to Paid invoices
    _open(page, erp_url, "/admin/invoice?filter_status=PAID")

    # Then the status is a pill that says Paid in the success tone
    pill = page.get_by_test_id("row-status").first
    expect(pill).to_have_text("Paid")
    expect(pill).to_have_class(re.compile(r"success"))


def test_sent_invoice_past_its_due_date_reads_overdue(page: Page, erp_url: str) -> None:
    """
    Scenario: overdue invoices are flagged
      Given a Sent invoice whose due date has passed
      Then  its status pill reads "Overdue" in the danger tone
    """
    # Given the Sent invoices due before today
    # (the oldest due dates first, so the first row is long overdue)
    _open(
        page,
        erp_url,
        "/admin/invoice?filter_status=SENT&sort_by=date_due&sort_direction=asc",
    )

    # Then the first one is flagged with text and tone
    pill = page.get_by_test_id("row-status").first
    expect(pill).to_have_text("Overdue")
    expect(pill).to_have_class(re.compile(r"danger"))


def test_card_shows_the_key_facts_first(page: Page, erp_url: str) -> None:
    """
    Scenario: card shows the key facts first
      Given the invoice list on a phone
      Then  amount and status sit on one line and at least six cards fit on a screen
      And   tapping the card opens the record
    """
    # Given the invoice list on a 393x852 phone
    page.set_viewport_size({"width": 393, "height": 852})
    _open(page, erp_url, "/admin/invoice")

    # Then the status pill and the amount share a line
    row = page.get_by_test_id("list-row").first
    pill_box = row.get_by_test_id("row-status").bounding_box()
    amount_box = row.get_by_role("cell").nth(-2).bounding_box()
    assert pill_box is not None
    assert amount_box is not None
    assert (
        abs((pill_box["y"] + pill_box["height"] / 2) - (amount_box["y"] + amount_box["height"] / 2))
        < 12
    )

    # And the title is the number followed by the customer, and the dates are secondary
    title = row.get_by_role("rowheader")
    customer = row.get_by_role("cell").nth(0)
    assert title.bounding_box()["y"] <= customer.bounding_box()["y"] + 4  # type: ignore[index]
    expect(customer).not_to_be_empty()
    date_colour = row.get_by_role("cell").nth(1).evaluate("el => getComputedStyle(el).color")
    title_colour = title.evaluate("el => getComputedStyle(el).color")
    assert date_colour != title_colour

    # And at least six cards are at least half visible on the first screen
    on_screen = 0
    for card in page.get_by_test_id("list-row").all():
        box = card.bounding_box()
        assert box is not None
        if box["y"] + box["height"] / 2 <= 852:
            on_screen += 1
    assert on_screen >= 6

    # And tapping the card opens the record
    row.get_by_test_id("row-link").click()
    expect(page).to_have_url(re.compile(r"/admin/invoice/\d+"))


def test_all_columns_are_reachable_on_a_tablet(page: Page, erp_url: str) -> None:
    """
    Scenario: all columns reachable on a tablet
      Given a 768x1024 viewport and the invoice list
      Then  the table shows a visible scroll shadow on the edge that hides columns
    """
    # Given a tablet viewport and the invoice list
    page.set_viewport_size({"width": 768, "height": 1024})
    _open(page, erp_url, "/admin/invoice")

    # Then every column is reachable: it fits, or the wrapper scrolls to the last header
    wrapper = page.get_by_test_id("list-table").locator("xpath=..")
    scrolls = wrapper.evaluate("el => el.scrollWidth > el.clientWidth")
    shadow = wrapper.evaluate("el => getComputedStyle(el).backgroundImage")
    assert "gradient" in shadow
    last = page.get_by_role("columnheader", name="Total Amount")
    if scrolls:
        last.scroll_into_view_if_needed()
    expect(last).to_be_in_viewport()
    expect(page.get_by_role("columnheader", name="Status")).to_be_attached()


def test_scroll_shadows_follow_dark_mode(page: Page, erp_url: str) -> None:
    """
    Scenario: scroll shadow covers match the table background in dark mode
      Given a 768px viewport in dark mode and the invoice list
      Then  the wrapper background colour is the surface the gradient covers use
    """
    # Given dark mode on a tablet
    page.emulate_media(color_scheme="dark")
    page.set_viewport_size({"width": 768, "height": 1024})
    _open(page, erp_url, "/admin/invoice")

    # Then the wrapper paints a gradient over its own (dark) background
    wrapper = page.get_by_test_id("list-table").locator("xpath=..")
    assert "gradient" in wrapper.evaluate("el => getComputedStyle(el).backgroundImage")
    colour = wrapper.evaluate("el => getComputedStyle(el).backgroundColor")
    channels = [int(c) for c in re.findall(r"\d+", colour)[:3]]
    assert max(channels) < 128


def test_consistent_naming(page: Page, erp_url: str) -> None:
    """
    Scenario: consistent naming
      Given the Profit & Loss report
      Then  the sidebar, page heading and browser tab all say "Profit & Loss"
    """
    # Given the report opened from the sidebar
    _login(page, erp_url)
    page.get_by_test_id("nav-erp-profit-loss").click()

    # Then the three names agree
    expect(page.get_by_test_id("nav-erp-profit-loss")).to_contain_text("Profit & Loss")
    expect(page.get_by_role("heading", name="Profit & Loss", level=1)).to_be_visible()
    expect(page).to_have_title(re.compile(r"Profit & Loss"))


def test_totals_are_one_row_per_pair_on_a_phone(page: Page, erp_url: str) -> None:
    """
    Scenario: totals render as label and value on one row on phones
      Given the report on a phone
      Then  "Total Revenue" and its value share a row
    """
    # Given the report on a 393x852 phone
    page.set_viewport_size({"width": 393, "height": 852})
    _login(page, erp_url)
    page.goto(erp_url + "/admin/erp/profit-loss")

    # Then the label and the value are on the same line
    label = page.get_by_role("rowheader", name="Total Revenue").bounding_box()
    value = page.get_by_test_id("total-revenue").bounding_box()
    assert label is not None
    assert value is not None
    assert abs(label["y"] - value["y"]) < 10


def test_invoice_list_offers_customer_and_due_date_filters(page: Page, erp_url: str) -> None:
    """
    Scenario: clerk finds overdue invoices quickly
      Given the invoice list
      Then  the filter sidebar offers customer, due-date and status filters
    """
    # Given the invoice list
    _open(page, erp_url, "/admin/invoice")

    # Then the sidebar has the customer, due-date, status and overdue filters
    sidebar = page.get_by_test_id("filter-sidebar")
    expect(sidebar).to_be_visible()
    expect(sidebar.get_by_text("Customer", exact=True).first).to_be_visible()
    expect(sidebar.get_by_text("Due date", exact=True).first).to_be_visible()
    expect(sidebar.get_by_text("Status", exact=True).first).to_be_visible()
    expect(sidebar.get_by_test_id("filter-overdue")).to_be_visible()


def test_overdue_filter_lists_only_overdue_invoices(page: Page, erp_url: str) -> None:
    """
    Scenario: overdue filter lists only invoices that read Overdue
      Given the invoice list
      When  the clerk turns on "Overdue only"
      Then  every row on the page shows the Overdue pill
    """
    # Given the invoice list
    _open(page, erp_url, "/admin/invoice")

    # When the clerk turns on Overdue only
    page.get_by_test_id("filter-overdue").check()
    page.get_by_test_id("filter-apply-btn").click()
    expect(page).to_have_url(re.compile(r"overdue=1"))

    # Then every row reads Overdue
    rows = page.get_by_test_id("list-row")
    expect(rows.first).to_be_visible()
    for row in rows.all():
        expect(row.get_by_test_id("row-status")).to_have_text("Overdue")


def test_page_size_selector_changes_rows_per_page(page: Page, erp_url: str) -> None:
    """
    Scenario: clerk picks how many invoices to see per page
      Given the invoice list with ten rows per page
      When  the clerk chooses 25 rows per page
      Then  the list shows 25 rows and the pager keeps that size on the next page
    """
    # Given the invoice list
    _open(page, erp_url, "/admin/invoice")
    expect(page.get_by_test_id("list-row")).to_have_count(10)

    # When the clerk chooses 25 rows per page
    page.get_by_test_id("page-size-25").click()

    # Then 25 rows show and the next page keeps the size
    expect(page.get_by_test_id("list-row")).to_have_count(25)
    page.get_by_test_id("pagination-next").click()
    expect(page.get_by_test_id("page-size-25")).to_have_attribute("aria-current", "true")


def test_mark_paid_bulk_action_settles_invoices(page: Page, erp_url: str) -> None:
    """
    Scenario: mark paid is a bulk action
      Given the Sent invoices
      When  a clerk selects one and runs "Mark paid"
      Then  one fewer invoice is Sent
    """
    # Given the Sent invoices
    _open(page, erp_url, "/admin/invoice?filter_status=SENT")
    info = page.get_by_test_id("pagination-info")
    before = int(re.search(r"of (\d+)", info.inner_text()).group(1))  # type: ignore[union-attr]

    # When a clerk selects the first row and runs Mark paid
    page.get_by_test_id("bulk-checkbox").first.check()
    page.get_by_label("Action for selected rows").select_option("mark_paid")
    page.get_by_role("button", name="Run").click()
    expect(page.get_by_test_id("bulk-result")).to_be_visible()

    # Then one fewer invoice is Sent
    page.goto(erp_url + "/admin/invoice?filter_status=SENT")
    expect(page.get_by_test_id("pagination-info")).to_contain_text(f"of {before - 1} results")


def test_mark_paid_refuses_a_cancelled_invoice(page: Page, erp_url: str) -> None:
    """
    Scenario: mark paid skips invoices that are not Sent
      Given the Cancelled invoices
      When  a clerk selects one and runs "Mark paid"
      Then  the row fails and the invoice stays Cancelled
    """
    # Given the Cancelled invoices
    _open(page, erp_url, "/admin/invoice?filter_status=CANCELLED")
    before = page.get_by_test_id("pagination-info").inner_text()

    # When a clerk selects the first row and runs Mark paid
    page.get_by_test_id("bulk-checkbox").first.check()
    page.get_by_label("Action for selected rows").select_option("mark_paid")
    page.get_by_role("button", name="Run").click()
    expect(page.get_by_test_id("bulk-result")).to_contain_text("Only Sent invoices")

    # Then the Cancelled count is unchanged
    page.goto(erp_url + "/admin/invoice?filter_status=CANCELLED")
    expect(page.get_by_test_id("pagination-info")).to_have_text(before)


def test_dashboard_answers_what_needs_attention(page: Page, erp_url: str) -> None:
    """
    Scenario: dashboard answers "what needs attention"
      Given the ERP dashboard
      Then  it shows open, overdue and due-this-week counts that link to filtered lists
    """
    # Given the dashboard
    _login(page, erp_url)

    # Then the counts are there and the overdue tile opens the filtered list
    expect(page.get_by_test_id("figure-open-invoices")).to_be_visible()
    expect(page.get_by_test_id("figure-due-this-week")).to_be_visible()
    overdue = page.get_by_test_id("figure-overdue-invoices")
    expect(overdue).to_be_visible()
    overdue.click()
    expect(page).to_have_url(re.compile(r"/admin/invoice\?filter_status=SENT&date_due__lte="))
    expect(page.get_by_test_id("list-row").first).to_be_visible()
