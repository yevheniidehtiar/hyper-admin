"""Unit/integration tests for BulkSeeder over SQLite (#248/#249)."""

import signal
from types import SimpleNamespace

import pytest
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
)

from hyperadmin.loadtest.batch import BulkSeeder, SeedInterruptedError, SeedSummary
from hyperadmin.loadtest.plan import SeedPlan, TablePlan


def _account_factory(pool, rng, seq):
    return {"name": f"Account {seq}"}


def _invoice_factory(pool, rng, seq):
    return {"number": f"INV-{seq:08d}", "account_id": pool.sample("accounts")}


def _plan(accounts=50, invoices=200):
    return SeedPlan(
        (
            TablePlan("accounts", accounts, _account_factory, ("name",)),
            TablePlan(
                "invoices",
                invoices,
                _invoice_factory,
                ("number", "account_id"),
                fk_parents=("accounts",),
                unique_columns=("number",),
            ),
        )
    )


@pytest.fixture
def engine(tmp_path):
    # File-based SQLite so reflection (separate connection) sees the schema.
    eng = create_engine(f"sqlite:///{tmp_path / 'erp.db'}")
    md = MetaData()
    Table("accounts", md, Column("id", Integer, primary_key=True), Column("name", String))
    Table(
        "invoices",
        md,
        Column("id", Integer, primary_key=True),
        Column("number", String, unique=True),
        Column("account_id", Integer, ForeignKey("accounts.id")),
    )
    md.create_all(eng)
    return eng


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(_reflect(engine, table))).scalar()


def _reflect(engine, name):
    return Table(name, MetaData(), autoload_with=engine)


def _seeder(plan, engine, tmp_path, **kw):
    kw.setdefault("install_signal_handlers", False)
    kw.setdefault("state_file", tmp_path / ".hyperadmin-seed.json")
    return BulkSeeder(plan=plan, engine=engine, **kw)


class TestSeedSummary:
    def test_rows_per_second(self):
        s = SeedSummary(rows_inserted=1000, elapsed_seconds=2.0)
        assert s.rows_per_second == 500.0

    def test_rows_per_second_zero_elapsed(self):
        assert SeedSummary(rows_inserted=10).rows_per_second == 0.0


class TestBasicSeeding:
    def test_seeds_all_rows(self, engine, tmp_path):
        """
        Scenario: bulk seed produces N rows across the plan
          Given a fresh SQLite database with the schema migrated
          When  the seeder runs with target 50 accounts + 200 invoices
          Then  each table contains its planned row count
        """
        summary = _seeder(_plan(), engine, tmp_path, batch_size=64).run()
        assert _count(engine, "accounts") == 50
        assert _count(engine, "invoices") == 200
        assert summary.rows_inserted == 250
        assert summary.per_table == {"accounts": 50, "invoices": 200}

    def test_throughput_is_reported(self, engine, tmp_path):
        summary = _seeder(_plan(10, 40), engine, tmp_path).run()
        assert summary.elapsed_seconds > 0
        assert summary.rows_per_second > 0

    def test_checkpoint_removed_on_clean_completion(self, engine, tmp_path):
        state_file = tmp_path / ".hyperadmin-seed.json"
        _seeder(_plan(10, 20), engine, tmp_path, state_file=state_file).run()
        assert not state_file.exists()


class TestForeignKeyIntegrity:
    def test_every_child_fk_points_at_a_real_parent(self, engine, tmp_path):
        """
        Scenario: foreign-key integrity is preserved across batches
          Given the plan inserts Accounts before Invoices
          When  the seeder commits the Invoices batches
          Then  every invoice.account_id references an existing account
        """
        _seeder(_plan(30, 300), engine, tmp_path, batch_size=50).run()
        accounts = _reflect(engine, "accounts")
        invoices = _reflect(engine, "invoices")
        with engine.connect() as conn:
            account_ids = set(conn.execute(select(accounts.c.id)).scalars())
            fk_ids = set(conn.execute(select(invoices.c.account_id)).scalars())
        assert fk_ids <= account_ids
        assert fk_ids  # non-empty: invoices really did reference parents

    def test_unique_column_has_no_collisions_across_batches(self, engine, tmp_path):
        # seq-derived unique values must stay unique even with a small batch size.
        _seeder(_plan(5, 137), engine, tmp_path, batch_size=10).run()
        invoices = _reflect(engine, "invoices")
        with engine.connect() as conn:
            numbers = conn.execute(select(invoices.c.number)).scalars().all()
        assert len(numbers) == len(set(numbers)) == 137


class TestResume:
    def test_interrupt_then_resume_completes_without_gaps_or_dupes(self, engine, tmp_path):
        """
        Scenario: Ctrl-C mid-run resumes from the last completed batch
          Given the seeder is interrupted after some invoice batches commit
          When  it is re-run with --resume
          Then  the final row count equals the target with no duplicates
          And   the checkpoint file is removed on clean completion
        """
        state_file = tmp_path / ".hyperadmin-seed.json"
        seeder_a = _seeder(_plan(20, 100), engine, tmp_path, batch_size=10, state_file=state_file)

        class Interrupting:
            def __init__(self, seeder):
                self.seeder = seeder
                self.done = 0

            def start_table(self, table, total):
                pass

            def advance(self, table, n):
                if table == "invoices":
                    self.done += n
                    if self.done >= 30:
                        self.seeder._interrupted = True

            def finish_table(self, table):
                pass

            def close(self):
                pass

        seeder_a.progress = Interrupting(seeder_a)
        with pytest.raises(SeedInterruptedError):
            seeder_a.run()
        assert state_file.exists()
        # Some but not all invoices committed.
        partial = _count(engine, "invoices")
        assert 0 < partial < 100

        seeder_b = _seeder(
            _plan(20, 100), engine, tmp_path, batch_size=10, state_file=state_file, resume=True
        )
        summary = seeder_b.run()
        assert _count(engine, "invoices") == 100
        assert summary.rows_inserted == 100 - partial  # only the remaining rows this run
        invoices = _reflect(engine, "invoices")
        with engine.connect() as conn:
            numbers = conn.execute(select(invoices.c.number)).scalars().all()
        assert len(numbers) == len(set(numbers)) == 100
        assert not state_file.exists()


class TestSignalHandling:
    def test_handlers_installed_and_restored(self, engine, tmp_path):
        before = signal.getsignal(signal.SIGINT)
        summary = _seeder(_plan(5, 10), engine, tmp_path, install_signal_handlers=True).run()
        assert summary.rows_inserted == 15
        # The seeder restores the original handler after a clean run.
        assert signal.getsignal(signal.SIGINT) is before

    def test_handle_signal_sets_interrupted_flag(self, engine, tmp_path):
        seeder = _seeder(_plan(), engine, tmp_path)
        assert seeder._interrupted is False
        seeder._handle_signal(signal.SIGINT, None)
        assert seeder._interrupted is True


class TestValidation:
    def test_zero_batch_size_rejected(self, engine, tmp_path):
        with pytest.raises(ValueError, match="batch_size must be >= 1"):
            _seeder(_plan(), engine, tmp_path, batch_size=0)

    def test_sqlite_batch_size_is_capped(self, engine, tmp_path):
        # max columns in plan = 2 (invoices) -> cap = 32766 // 2 = 16383.
        seeder = _seeder(_plan(), engine, tmp_path, batch_size=100_000)
        assert seeder.batch_size == 16383

    def test_non_sqlite_batch_size_passthrough(self, tmp_path):
        # Only SQLite shrinks the batch size; other dialects pass it through unchanged.
        fake_engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        seeder = _seeder(_plan(), fake_engine, tmp_path, batch_size=99_999)
        assert seeder.batch_size == 99_999

    def test_composite_pk_table_rejected(self, tmp_path):
        eng = create_engine(f"sqlite:///{tmp_path / 'composite.db'}")
        md = MetaData()
        Table(
            "composite",
            md,
            Column("a", Integer, primary_key=True),
            Column("b", Integer, primary_key=True),
        )
        md.create_all(eng)
        tbl = _reflect(eng, "composite")
        with pytest.raises(ValueError, match="exactly one primary-key column"):
            BulkSeeder._pk_column(tbl)
