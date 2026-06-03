"""Integration test for the bulk seeder against the real ERP schema (#255).

Not a browser test — it exercises ``BulkSeeder``, the ``hyperadmin seed`` CLI, and the
``examples/erp`` async wrapper end-to-end against a file-backed SQLite database. It lives under
``tests/e2e`` per the SDD because it validates the full seeding stack, not a single unit.
"""

import subprocess
import sys

# Importing the models registers them on SQLModel.metadata so create_all builds erp_* tables.
import examples.erp.accounting.models
import examples.erp.contacts.models
import examples.erp.purchases.models
import examples.erp.sales.models  # noqa: F401
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlmodel import SQLModel

from hyperadmin.loadtest import BulkSeeder
from hyperadmin.loadtest.generators import build_plan

# (child table, FK column) -> (parent table, parent PK) edges of the ERP plan.
_FK_EDGES = [
    ("erp_invoices", "customer_id", "erp_contacts", "id"),
    ("erp_invoice_items", "invoice_id", "erp_invoices", "id"),
    ("erp_bills", "supplier_id", "erp_contacts", "id"),
    ("erp_bill_items", "bill_id", "erp_bills", "id"),
    ("erp_journal_lines", "entry_id", "erp_journal_entries", "id"),
    ("erp_journal_lines", "account_id", "erp_accounts", "id"),
]


def _create_schema(db_path) -> str:
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    return url


def _row_count(engine, table) -> int:
    tbl = Table(table, MetaData(), autoload_with=engine)
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(tbl)).scalar()


def _assert_fk_integrity(engine) -> None:
    md = MetaData()
    for child, fk_col, parent, pk_col in _FK_EDGES:
        child_tbl = Table(child, md, autoload_with=engine)
        parent_tbl = Table(parent, md, autoload_with=engine)
        with engine.connect() as conn:
            fk_values = set(conn.execute(select(child_tbl.c[fk_col])).scalars())
            parent_ids = set(conn.execute(select(parent_tbl.c[pk_col])).scalars())
        assert fk_values <= parent_ids, f"{child}.{fk_col} has orphan references to {parent}"


def test_seed_1k_records_preserves_fk_integrity(tmp_path):
    """
    Scenario: seed 1K records into SQLite, verify FK integrity
      Given a fresh SQLite database with the ERP schema migrated
      When  the bulk seeder runs with a total target of 1000 rows
      Then  the tables hold 1000 rows in total
      And   every foreign key references an existing parent row
    """
    # Given a fresh SQLite database with the ERP schema migrated
    url = _create_schema(tmp_path / "erp.db")
    engine = create_engine(url)
    plan = build_plan("erp", seed=42).scaled(1000)

    # When the bulk seeder runs with a total target of 1000 rows
    summary = BulkSeeder(
        plan=plan,
        engine=engine,
        batch_size=250,
        state_file=tmp_path / ".hyperadmin-seed.json",
        install_signal_handlers=False,
    ).run()

    # Then the tables hold 1000 rows in total
    assert summary.rows_inserted == 1000
    total = sum(_row_count(engine, t.name) for t in plan.tables)
    assert total == 1000

    # And every foreign key references an existing parent row
    _assert_fk_integrity(engine)
    engine.dispose()


def test_cli_seeds_into_sqlite(tmp_path):
    """The ``hyperadmin seed`` CLI seeds a pre-migrated database and exits 0."""
    url = _create_schema(tmp_path / "erp.db")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hyperadmin",
            "seed",
            "--count",
            "500",
            "--plan",
            "erp",
            "--database-url",
            url,
            "--batch-size",
            "200",
            "--no-progress",
            "--state-file",
            str(tmp_path / ".seed.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Seeded 500 rows" in result.stdout + result.stderr

    engine = create_engine(url)
    total = sum(_row_count(engine, t.name) for t in build_plan("erp").scaled(500).tables)
    assert total == 500
    _assert_fk_integrity(engine)
    engine.dispose()


def test_examples_bulk_seed_wrapper(tmp_path):
    """The async ``bulk_seed_erp`` wrapper creates the schema and seeds via a worker thread.

    Run synchronously in a dedicated thread (fresh event loop) rather than as an ``async def``
    test: the e2e suite activates both pytest-asyncio (auto mode) and the anyio plugin, and a
    plain coroutine test gets claimed by both runners, which collide on loop teardown with
    "Cannot run the event loop while another loop is running". A sync test sidesteps both.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from examples.erp.seed import bulk_seed_erp

    url = f"sqlite:///{tmp_path / 'wrapped.db'}"
    with ThreadPoolExecutor(max_workers=1) as executor:
        summary = executor.submit(
            lambda: asyncio.run(bulk_seed_erp(300, batch_size=100, database_url=url))
        ).result()
    assert summary.rows_inserted == 300

    engine = create_engine(url)
    total = sum(_row_count(engine, t.name) for t in build_plan("erp").scaled(300).tables)
    assert total == 300
    _assert_fk_integrity(engine)
    engine.dispose()
