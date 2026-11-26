"""E2E scalability smoke tests on a seeded dataset (#243).

Companion app: :mod:`tests.e2e.apps.scalability`. The synthetic data generator
(:mod:`hyperadmin.loadtest`) seeds 12,605 rows across four related tables once per test
session; every test runs against its own copy of that SQLite file.

The tests assert on behaviour and on the SQL each page runs (read from the app's
``/_test/queries`` route), not on wall-clock time: a shared CI runner makes timings
meaningless, while "one query for the relation whatever the page size" or "no ``count(*)``
on the second request" stays true on any machine.

Opt-in large run (skipped by default)::

    E2E_SCALABILITY_SCALE=100 E2E_SCALABILITY_TIMING=1 uv run pytest tests/e2e/test_scalability.py

``E2E_SCALABILITY_SCALE`` multiplies the two large tables (100 gives 1.2 million rows) and
``E2E_SCALABILITY_TIMING=1`` turns on the one test that checks response times.

Selectors follow ``CLAUDE.md``: role, label, text, then test id. No ``ha-*`` classes.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest
from playwright.sync_api import Locator, Page, expect

from hyperadmin.core.adapters import encode_cursor
from tests.e2e.apps.scalability_models import MOVEMENTS, PRODUCTS, scale, seed_database

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

PRODUCT = "/admin/product"
MOVEMENT = "/admin/movement"

SCALE = scale()
PRODUCT_ROWS = PRODUCTS * SCALE
MOVEMENT_ROWS = MOVEMENTS * SCALE
PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
# Story #243 asks for pages that load in under two seconds; only the opt-in run checks it.
RESPONSE_BUDGET_SECONDS = 2.0
# Seeded servers answer slower on a loaded runner; rows appear once the swap lands.
SWAP_TIMEOUT_MS = 15_000


@pytest.fixture(scope="session")
def scalability_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Seed the dataset once per test session (per xdist worker) and return the SQLite file."""
    path = tmp_path_factory.mktemp("scalability") / "template.db"
    seed_database(path, SCALE)
    return path


@pytest.fixture
def scalability_db(scalability_template: Path, tmp_path: Path) -> Path:
    """A private copy of the seeded database, so a test that writes cannot affect another."""
    return shutil.copy(scalability_template, tmp_path / "scalability.db")


@pytest.fixture
def scalability_base_url(scalability_db: Path, start_server: Callable[..., str]) -> str:
    """Start the scalability app on this test's database copy and yield the base URL."""
    return start_server(
        "tests.e2e.apps.scalability", extra_env={"E2E_SCALABILITY_DB": str(scalability_db)}
    )


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _reset(page: Page, base_url: str) -> None:
    """Forget the SQL recorded so far."""
    response = page.request.post(f"{base_url}/_test/reset")
    assert response.status == HTTPStatus.OK, response.text()


def _statements(page: Page, base_url: str, table: str | None = None) -> list[dict[str, Any]]:
    """SQL run since the last reset; with ``table``, only statements that read from it."""
    statements = page.request.get(f"{base_url}/_test/queries").json()["statements"]
    if table is None:
        return statements
    return [s for s in statements if f"FROM {table}" in s["sql"]]


def _counts(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in statements if s["sql"].startswith("SELECT count(")]


def _rows(page: Page) -> Locator:
    return page.get_by_test_id("list-row")


def _query(db: Path, sql: str, *params: Any) -> Any:
    """First column of the first row of ``sql`` on the test's database."""
    with sqlite3.connect(db) as conn:
        return conn.execute(sql, params).fetchone()[0]


def _sku(pk: int) -> str:
    return f"SKU-{pk - 1:07d}"


def _reference(pk: int) -> str:
    return f"MOV-{pk - 1:07d}"


def test_list_page_loads_its_relation_in_one_query_whatever_the_page_size(
    page: Page, scalability_base_url: str, scalability_db: Path
) -> None:
    """
    Scenario: list page loads its relation in one query whatever the page size
      Given 9,000 products, each with one of 600 suppliers, and a list that shows the supplier
      When  the user opens the list with 10 rows and then with 100 rows per page
      Then  both pages run the same number of SQL statements
      And   the suppliers of a page are read with one statement
      And   each row shows its supplier's name
    """
    # Given 9,000 products with suppliers; one visit fills the count and filter caches
    _login(page, scalability_base_url)
    page.goto(f"{scalability_base_url}{PRODUCT}?page_size={PAGE_SIZE}")

    # When the user opens the list with 10 rows and then with 100 rows per page
    _reset(page, scalability_base_url)
    page.goto(f"{scalability_base_url}{PRODUCT}?page_size={PAGE_SIZE}")
    expect(_rows(page)).to_have_count(PAGE_SIZE)
    small_page = _statements(page, scalability_base_url)
    _reset(page, scalability_base_url)
    page.goto(f"{scalability_base_url}{PRODUCT}?page_size={MAX_PAGE_SIZE}")
    expect(_rows(page)).to_have_count(MAX_PAGE_SIZE)
    large_page = _statements(page, scalability_base_url)

    # Then both pages run the same number of SQL statements
    assert len(large_page) == len(small_page), [s["sql"] for s in large_page]

    # And the suppliers of a page are read with one statement
    supplier_reads = [s for s in large_page if "FROM e2e_sc_supplier" in s["sql"]]
    assert len(supplier_reads) == 1, [s["sql"] for s in supplier_reads]
    assert "e2e_sc_supplier.id IN (" in supplier_reads[0]["sql"]

    # And each row shows its supplier's name
    supplier = _query(
        scalability_db,
        "SELECT s.name FROM e2e_sc_product p JOIN e2e_sc_supplier s ON s.id = p.supplier_id "
        "WHERE p.id = ?",
        MAX_PAGE_SIZE,
    )
    expect(_rows(page).filter(has_text=_sku(MAX_PAGE_SIZE))).to_contain_text(supplier)


def test_list_total_is_counted_once_for_repeated_requests(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: list total is counted once for repeated requests
      Given a product list with `count_cache_ttl=60`
      When  the user opens page 1 and then page 2
      Then  page 1 counts the table once
      And   page 2 shows the same total without counting again
    """
    # Given a product list with count_cache_ttl=60
    _login(page, scalability_base_url)
    _reset(page, scalability_base_url)

    # When the user opens page 1
    page.goto(scalability_base_url + PRODUCT)

    # Then page 1 counts the table once
    info = page.get_by_test_id("pagination-info")
    expect(info).to_contain_text(f"Showing 1 to 10 of {PRODUCT_ROWS} results")
    assert len(_counts(_statements(page, scalability_base_url, "(SELECT e2e_sc_product"))) == 1

    # When the user opens page 2
    _reset(page, scalability_base_url)
    page.get_by_test_id("pagination-next").click()

    # Then page 2 shows the same total without counting again
    expect(info).to_contain_text(f"Showing 11 to 20 of {PRODUCT_ROWS} results")
    assert _counts(_statements(page, scalability_base_url)) == []


def test_a_row_created_in_the_admin_shows_in_the_cached_total_at_once(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: a row created in the admin shows in the cached total at once
      Given a product list whose total of 9,000 is cached for 60 seconds
      When  the user creates a product through the admin
      Then  the list total is 9,001
    """
    # Given a product list whose total is cached for 60 seconds
    _login(page, scalability_base_url)
    page.goto(scalability_base_url + PRODUCT)
    info = page.get_by_test_id("pagination-info")
    expect(info).to_contain_text(f"of {PRODUCT_ROWS} results")

    # When the user creates a product through the admin
    page.get_by_test_id("create-link").click()
    page.get_by_label("Sku").fill("SKU-NEW")
    page.get_by_label("Name").fill("Fresh product")
    page.get_by_role("button", name="Create").click()
    expect(page).not_to_have_url(f"{scalability_base_url}{PRODUCT}/create")

    # Then the list total is 9,001
    page.goto(scalability_base_url + PRODUCT)
    expect(info).to_contain_text(f"of {PRODUCT_ROWS + 1} results")


def test_foreign_key_to_a_large_table_is_a_lazy_autocomplete(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: foreign key to a large table is a lazy autocomplete
      Given 600 suppliers (above `preload_threshold`) and 5 warehouses (below it)
      When  the user opens the product create form
      Then  the Supplier field carries no preloaded option and no supplier row was read
      And   the Warehouse field carries all 5 warehouses
      And   typing "Supplier 0420" fetches the match, which the user can pick
    """
    # Given 600 suppliers and 5 warehouses
    _login(page, scalability_base_url)
    _reset(page, scalability_base_url)

    # When the user opens the product create form
    page.goto(f"{scalability_base_url}{PRODUCT}/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()

    # Then the Supplier field carries no preloaded option (only the blank one) ...
    supplier_select = page.get_by_test_id("autocomplete-select-supplier_id")
    assert supplier_select.evaluate("el => el.options.length") == 1
    # ... and no supplier row was read: the only supplier statement is the size check
    supplier_reads = _statements(page, scalability_base_url, "e2e_sc_supplier")
    assert supplier_reads == _counts(supplier_reads), [s["sql"] for s in supplier_reads]

    # And the Warehouse field carries all 5 warehouses (plus the blank option)
    warehouse_select = page.get_by_test_id("autocomplete-select-warehouse_id")
    assert warehouse_select.evaluate("el => el.options.length") == 5 + 1

    # And typing fetches the match, which the user can pick
    supplier = page.get_by_role("combobox", name="Supplier")
    with page.expect_response(lambda r: "choices/supplier" in r.url and "q=" in r.url):
        supplier.fill("Supplier 0420")
    expect(supplier).to_have_attribute("aria-expanded", "true")
    supplier.press("ArrowDown")
    supplier.press("Enter")
    expect(supplier).to_have_value("Supplier 0420")
    expect(supplier_select).to_have_value("420")


def test_keyset_pagination_pages_forward_and_back_from_a_deep_page(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: keyset pagination pages forward and back from a deep page
      Given 3,000 movements listed with `pagination_mode="cursor"`
      When  the user opens the page that starts 25 rows before the end and pages forward
      Then  the deep page is read by key, without skipping rows and without a count
      And   Next shows the following 10 rows, then the last 5 with no Next link
      And   Previous returns to the same 10 rows
    """
    # Given 3,000 movements listed with pagination_mode="cursor"
    _login(page, scalability_base_url)
    page.goto(scalability_base_url + MOVEMENT)
    expect(_rows(page).first).to_contain_text(_reference(1))
    expect(page.get_by_test_id("pagination-info")).not_to_contain_text("results")
    expect(page.get_by_test_id("pagination-prev")).to_have_count(0)

    # When the user opens the page that starts 25 rows before the end
    after = MOVEMENT_ROWS - 25
    _reset(page, scalability_base_url)
    page.goto(f"{scalability_base_url}{MOVEMENT}?cursor={encode_cursor(after, after, 'next')}")

    # Then the deep page is read by key, without skipping rows and without a count
    expect(_rows(page)).to_have_count(PAGE_SIZE)
    expect(_rows(page).first).to_contain_text(_reference(after + 1))
    expect(_rows(page).last).to_contain_text(_reference(after + PAGE_SIZE))
    reads = _statements(page, scalability_base_url, "e2e_sc_movement")
    assert len(reads) == 1, [s["sql"] for s in reads]
    assert "e2e_sc_movement.id > ?" in reads[0]["sql"]
    assert reads[0]["params"][0] == str(after)
    if "OFFSET" in reads[0]["sql"]:  # SQLite always renders OFFSET next to LIMIT
        assert reads[0]["params"][-1] == "0"

    # And Next shows the following 10 rows
    page.get_by_test_id("pagination-next").click()
    expect(_rows(page).first).to_contain_text(_reference(after + 11), timeout=SWAP_TIMEOUT_MS)
    expect(_rows(page)).to_have_count(PAGE_SIZE)

    # ... then the last 5 with no Next link
    page.get_by_test_id("pagination-next").click()
    expect(_rows(page).first).to_contain_text(_reference(after + 21), timeout=SWAP_TIMEOUT_MS)
    expect(_rows(page)).to_have_count(5)
    expect(_rows(page).last).to_contain_text(_reference(MOVEMENT_ROWS))
    expect(page.get_by_test_id("pagination-next")).to_have_count(0)

    # And Previous returns to the same 10 rows
    page.get_by_test_id("pagination-prev").click()
    expect(_rows(page).first).to_contain_text(_reference(after + 11), timeout=SWAP_TIMEOUT_MS)
    expect(_rows(page).last).to_contain_text(_reference(after + 20))
    expect(_rows(page)).to_have_count(PAGE_SIZE)


def test_search_finds_a_row_through_the_configured_search_fields(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: search finds a row through the configured search fields
      Given 9,000 products whose admin sets `search_fields=["sku"]`
      When  the user searches for "SKU-0004242"
      Then  the list shows that one product
      And   the search compares the `sku` column only
    """
    # Given 9,000 products whose admin searches the sku column only
    _login(page, scalability_base_url)
    page.goto(scalability_base_url + PRODUCT)
    _reset(page, scalability_base_url)

    # When the user searches for one SKU
    page.get_by_test_id("search-input").press_sequentially("SKU-0004242")

    # Then the list shows that one product
    expect(_rows(page)).to_have_count(1, timeout=SWAP_TIMEOUT_MS)
    expect(_rows(page)).to_contain_text("Product 0004242")
    expect(page.get_by_test_id("pagination-info")).to_contain_text("of 1 results")

    # And the search compares the sku column only
    searches = [
        s["sql"]
        for s in _statements(page, scalability_base_url, "e2e_sc_product")
        if " LIKE " in s["sql"]
    ]
    assert searches, "the search ran no LIKE statement"
    for sql in searches:
        assert "e2e_sc_product.sku LIKE" in sql  # plain LIKE on SQLite: no lower() per row
        assert "e2e_sc_product.name LIKE" not in sql


def test_search_ignores_columns_outside_the_configured_search_fields(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: search ignores columns outside the configured search fields
      Given 9,000 products whose admin sets `search_fields=["sku"]`
      When  the user searches for the product name "Product 0004242"
      Then  the list shows no product
    """
    # Given 9,000 products whose admin searches the sku column only
    _login(page, scalability_base_url)
    page.goto(scalability_base_url + PRODUCT)
    expect(_rows(page)).to_have_count(PAGE_SIZE)

    # When the user searches for a product name
    with page.expect_response(lambda r: "0004242" in r.url):
        page.get_by_test_id("search-input").press_sequentially("Product 0004242")

    # Then the list shows no product
    expect(_rows(page)).to_have_count(0, timeout=SWAP_TIMEOUT_MS)


def test_filter_choices_are_read_once_and_reused(
    page: Page, scalability_base_url: str, scalability_db: Path
) -> None:
    """
    Scenario: filter choices are read once and reused
      Given a product list with a Warehouse filter and the default `filter_cache_ttl`
      When  the user opens the list twice
      Then  the first render reads the warehouses and the second reads none
      And   the filter still lists the 5 warehouses and narrows the list when one is chosen
    """
    # Given a product list with a Warehouse filter
    _login(page, scalability_base_url)
    _reset(page, scalability_base_url)

    # When the user opens the list twice
    page.goto(scalability_base_url + PRODUCT)
    first = _statements(page, scalability_base_url, "e2e_sc_warehouse")
    _reset(page, scalability_base_url)
    page.goto(scalability_base_url + PRODUCT)
    second = _statements(page, scalability_base_url, "e2e_sc_warehouse")

    # Then the first render reads the warehouses and the second reads none
    assert first, "the first render never read the filter choices"
    assert second == [], [s["sql"] for s in second]

    # And the filter still lists the 5 warehouses (plus "Any") ...
    page.get_by_role("button", name="Filters").click()
    warehouse = page.get_by_label("Warehouse", exact=True)
    assert warehouse.evaluate("el => el.options.length") == 5 + 1

    # ... and narrows the list when one is chosen
    expected = _query(scalability_db, "SELECT count(*) FROM e2e_sc_product WHERE warehouse_id = 2")
    warehouse.select_option(label="Warehouse 2")
    expect(page.get_by_test_id("pagination-info")).to_contain_text(
        f"of {expected} results", timeout=SWAP_TIMEOUT_MS
    )


def test_offset_pagination_still_shows_page_numbers_and_a_total_on_a_deep_page(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: offset pagination still shows page numbers and a total on a deep page
      Given 9,000 products listed with the default `pagination_mode="offset"`
      When  the user opens the last page by its number
      Then  the pager shows "Page 900 of 900" and the total of 9,000
      And   the last product is listed and there is no Next link
      And   Previous opens page 899
    """
    # Given 9,000 products listed with the default pagination mode
    _login(page, scalability_base_url)
    last_page = PRODUCT_ROWS // PAGE_SIZE

    # When the user opens the last page by its number
    page.goto(f"{scalability_base_url}{PRODUCT}?page={last_page}")

    # Then the pager shows the page number and the total
    expect(page.get_by_test_id("pagination-page")).to_contain_text(
        f"Page {last_page} of {last_page}"
    )
    expect(page.get_by_test_id("pagination-info")).to_contain_text(
        f"Showing {PRODUCT_ROWS - PAGE_SIZE + 1} to {PRODUCT_ROWS} of {PRODUCT_ROWS} results"
    )

    # And the last product is listed and there is no Next link
    expect(_rows(page).last).to_contain_text(_sku(PRODUCT_ROWS))
    expect(page.get_by_test_id("pagination-next")).to_have_count(0)

    # And Previous opens page 899
    page.get_by_test_id("pagination-prev").click()
    expect(page.get_by_test_id("pagination-page")).to_contain_text(
        f"Page {last_page - 1} of {last_page}", timeout=SWAP_TIMEOUT_MS
    )
    expect(_rows(page).last).to_contain_text(_sku(PRODUCT_ROWS - PAGE_SIZE))


@pytest.mark.skipif(
    os.environ.get("E2E_SCALABILITY_TIMING") != "1",
    reason="timing check is opt-in: set E2E_SCALABILITY_TIMING=1 on an idle machine",
)
def test_list_search_and_deep_pages_answer_within_two_seconds(
    page: Page, scalability_base_url: str
) -> None:
    """
    Scenario: list, search and deep pages answer within two seconds
      Given the seeded dataset (scaled by `E2E_SCALABILITY_SCALE`) on an idle machine
      When  the user opens the product list, a search, and a deep keyset page
      Then  each response arrives within two seconds
    """
    # Given the seeded dataset; one visit per list fills the caches a running admin has
    _login(page, scalability_base_url)
    page.goto(scalability_base_url + PRODUCT)
    page.goto(scalability_base_url + MOVEMENT)
    after = MOVEMENT_ROWS - 25
    urls = {
        "list": f"{PRODUCT}?page_size={MAX_PAGE_SIZE}",
        "search": f"{PRODUCT}?search={_sku(PRODUCT_ROWS // 2)}",
        "deep keyset page": f"{MOVEMENT}?cursor={encode_cursor(after, after, 'next')}",
    }

    for name, url in urls.items():
        # When the user opens the page
        started = time.monotonic()
        response = page.request.get(scalability_base_url + url)
        elapsed = time.monotonic() - started

        # Then the response arrives within two seconds
        assert response.status == HTTPStatus.OK, name
        assert elapsed < RESPONSE_BUDGET_SECONDS, f"{name} took {elapsed:.2f}s"
