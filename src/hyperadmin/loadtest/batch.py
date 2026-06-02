"""The bulk seeder: generate → batch → insert, with FK pooling and resumability.

``BulkSeeder.run()`` walks the plan in parent-before-child order. For each table it generates
rows via the table's ``row_factory``, inserts them with SQLAlchemy Core ``insert()`` in
batches, and commits per batch. After a parent table completes (or on resume) its primary keys
are loaded into the :class:`~hyperadmin.loadtest.pool.FKPool` so child tables can sample
skewed references. Progress is checkpointed after every committed batch so a kill can resume.

The seeder is **synchronous** by design — ``insert()`` is a sync API. The ERP example bridges
it onto its async event loop with :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import random
import signal
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import Engine, MetaData, Table, insert, select

from hyperadmin.loadtest.checkpoint import (
    CheckpointState,
    CheckpointStore,
    TableProgress,
    validate_resume,
)
from hyperadmin.loadtest.pool import FKPool

if TYPE_CHECKING:
    from hyperadmin.loadtest.plan import SeedPlan, TablePlan
    from hyperadmin.loadtest.progress import ProgressReporter

# SQLite caps host parameters per statement. 32766 is the modern limit (>= 3.32); we shrink
# the batch size to stay under it rather than letting inserts fail.
_SQLITE_MAX_PARAMS = 32766
# fsync the checkpoint every N committed batches — cheap per-batch JSON write, amortised fsync.
_FSYNC_EVERY = 100


class SeedInterruptedError(RuntimeError):
    """Raised when a SIGINT/SIGTERM is honoured after the in-flight batch commits."""

    def __init__(self, summary: SeedSummary) -> None:
        super().__init__("seeding interrupted; checkpoint saved — re-run with --resume")
        self.summary = summary


@dataclass
class SeedSummary:
    """Outcome of a :meth:`BulkSeeder.run` call."""

    rows_inserted: int = 0
    elapsed_seconds: float = 0.0
    per_table: dict[str, int] = field(default_factory=dict)

    @property
    def rows_per_second(self) -> float:
        return self.rows_inserted / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0

    def record(self, table: str, n: int) -> None:
        self.per_table[table] = self.per_table.get(table, 0) + n
        self.rows_inserted += n


class BulkSeeder:
    def __init__(  # noqa: PLR0913 - public seeder API; all knobs are keyword-only
        self,
        *,
        plan: SeedPlan,
        engine: Engine,
        batch_size: int = 5000,
        rng_seed: int = 42,
        state_file: Path = Path(".hyperadmin-seed.json"),
        resume: bool = False,
        progress: ProgressReporter | None = None,
        install_signal_handlers: bool = True,
    ) -> None:
        self.plan = plan
        self.engine = engine
        self.rng_seed = rng_seed
        self.resume = resume
        self.progress = progress
        self._install_signal_handlers = install_signal_handlers
        self._store = CheckpointStore(state_file)
        self.batch_size = self._effective_batch_size(batch_size)
        self._interrupted = False
        self._tables: dict[str, Table] = {}

    # -- public API ---------------------------------------------------------------------

    def run(self) -> SeedSummary:
        rng = random.Random(self.rng_seed)  # noqa: S311 - seeding, not cryptography
        pool = FKPool(pareto_a=self.plan.pareto_a, rng=rng)
        state = self._load_or_init_state()
        summary = SeedSummary()
        start = time.monotonic()

        with self._signal_guard(), self.engine.connect() as conn:
            for table in self.plan.tables:
                self._ensure_parents_loaded(conn, pool, table)
                self._seed_table(conn, pool, table, state, rng, summary)
                self._load_into_pool_if_parent(conn, pool, table)

        summary.elapsed_seconds = time.monotonic() - start
        # Clean completion: drop the checkpoint so the next run starts fresh.
        self._store.remove()
        if self.progress is not None:
            self.progress.close()
        return summary

    # -- per-table seeding --------------------------------------------------------------

    def _seed_table(
        self,
        conn: sqlalchemy.Connection,
        pool: FKPool,
        table: TablePlan,
        state: CheckpointState,
        rng,
        summary: SeedSummary,
    ) -> None:
        progress = state.tables[table.name]
        target = progress.target
        if self.progress is not None:
            self.progress.start_table(table.name, target)
            if progress.completed:
                self.progress.advance(table.name, progress.completed)

        tbl = self._reflect(table.name)
        while progress.completed < target:
            count = min(self.batch_size, target - progress.completed)
            rows = self._generate_batch(pool, table, rng, progress.completed, count)
            conn.execute(insert(tbl), rows)
            conn.commit()

            progress.completed += count
            progress.last_pk = progress.completed
            summary.record(table.name, count)
            if self.progress is not None:
                self.progress.advance(table.name, count)
            self._checkpoint(state, summary)

        if self.progress is not None:
            self.progress.finish_table(table.name)

    def _generate_batch(
        self, pool: FKPool, table: TablePlan, rng, start_seq: int, count: int
    ) -> list[dict]:
        """Build ``count`` row dicts. Unique columns derive from the global ``seq`` so values
        never collide across batches (see the seq-prefix decision in the SDD)."""
        factory = table.row_factory
        return [factory(pool, rng, start_seq + offset) for offset in range(count)]

    # -- FK pool population --------------------------------------------------------------

    def _ensure_parents_loaded(
        self, conn: sqlalchemy.Connection, pool: FKPool, table: TablePlan
    ) -> None:
        for parent in table.fk_parents:
            if pool.size(parent) == 0:
                self._load_parent_pks(conn, pool, parent)

    def _load_into_pool_if_parent(
        self, conn: sqlalchemy.Connection, pool: FKPool, table: TablePlan
    ) -> None:
        is_parent = any(table.name in other.fk_parents for other in self.plan.tables)
        if is_parent and pool.size(table.name) == 0:
            self._load_parent_pks(conn, pool, table.name)

    def _load_parent_pks(self, conn: sqlalchemy.Connection, pool: FKPool, name: str) -> None:
        tbl = self._reflect(name)
        pk_col = self._pk_column(tbl)
        pks = conn.execute(select(pk_col)).scalars().all()
        pool.extend(name, pks)

    # -- state & checkpointing -----------------------------------------------------------

    def _load_or_init_state(self) -> CheckpointState:
        if self.resume and self._store.exists():
            state = self._store.load()
            validate_resume(state, self.plan)
            return state
        # Fresh run: targets come straight from the plan.
        tables = {t.name: TableProgress(target=t.target_count) for t in self.plan.tables}
        state = CheckpointState(
            plan_hash=self.plan.hash(),
            rng_seed=self.rng_seed,
            started_at=_utc_now_iso(),
            tables=tables,
        )
        self._store.save(state, fsync=True)
        self._batch_counter = 0
        return state

    def _checkpoint(self, state: CheckpointState, summary: SeedSummary) -> None:
        self._batch_counter = getattr(self, "_batch_counter", 0) + 1
        fsync = self._batch_counter % _FSYNC_EVERY == 0
        self._store.save(state, fsync=fsync)
        if self._interrupted:
            self._store.save(state, fsync=True)
            summary.elapsed_seconds = 0.0
            raise SeedInterruptedError(summary)

    # -- reflection helpers --------------------------------------------------------------

    def _reflect(self, name: str) -> Table:
        if name not in self._tables:
            md = MetaData()
            self._tables[name] = Table(name, md, autoload_with=self.engine)
        return self._tables[name]

    @staticmethod
    def _pk_column(tbl: Table):
        pk_cols = list(tbl.primary_key.columns)
        if len(pk_cols) != 1:
            raise ValueError(
                f"table {tbl.name!r} must have exactly one primary-key column "
                f"to be seeded (found {len(pk_cols)})"
            )
        return pk_cols[0]

    def _effective_batch_size(self, batch_size: int) -> int:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.engine.dialect.name != "sqlite":
            return batch_size
        max_cols = max(len(t.columns) for t in self.plan.tables)
        cap = max(1, _SQLITE_MAX_PARAMS // max_cols)
        return min(batch_size, cap)

    # -- signal handling -----------------------------------------------------------------

    @contextmanager
    def _signal_guard(self):
        """Install cooperative SIGINT/SIGTERM handlers, restoring the originals on exit."""
        if not self._install_signal_handlers:
            yield
            return
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        for sig in previous:
            signal.signal(sig, self._handle_signal)
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    def _handle_signal(self, signum, frame) -> None:  # noqa: ARG002 - signal handler ABI
        # Cooperative: let the in-flight batch finish, then checkpoint+exit at the next check.
        self._interrupted = True


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["BulkSeeder", "SeedInterruptedError", "SeedSummary"]
