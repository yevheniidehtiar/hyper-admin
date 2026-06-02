"""Resumable seeding via a JSON checkpoint file.

The checkpoint records per-table progress after every committed batch. On ``--resume`` the
seeder loads it, verifies the plan has not drifted (``plan_hash``), and continues each table
from its ``completed`` count. The file is human-readable and diff-able; it is removed on clean
completion. Writes are atomic (temp file + ``os.replace``); ``fsync`` is amortised by the
caller (every N batches) to keep throughput high while bounding worst-case loss.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hyperadmin.loadtest.plan import SeedPlan


class PlanHashMismatchError(RuntimeError):
    """Raised when a ``--resume`` checkpoint does not match the current plan."""


@dataclass
class TableProgress:
    target: int
    completed: int = 0
    last_pk: int | None = None

    @property
    def remaining(self) -> int:
        return max(0, self.target - self.completed)

    @property
    def is_done(self) -> bool:
        return self.completed >= self.target


@dataclass
class CheckpointState:
    plan_hash: str
    rng_seed: int
    started_at: str
    tables: dict[str, TableProgress] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plan_hash": self.plan_hash,
            "rng_seed": self.rng_seed,
            "started_at": self.started_at,
            "tables": {
                name: {
                    "target": p.target,
                    "completed": p.completed,
                    "last_pk": p.last_pk,
                }
                for name, p in self.tables.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> CheckpointState:
        try:
            tables = {
                name: TableProgress(
                    target=int(tp["target"]),
                    completed=int(tp["completed"]),
                    last_pk=tp["last_pk"],
                )
                for name, tp in data["tables"].items()
            }
            return cls(
                plan_hash=str(data["plan_hash"]),
                rng_seed=int(data["rng_seed"]),
                started_at=str(data["started_at"]),
                tables=tables,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"corrupt checkpoint file: {exc}") from exc


class CheckpointStore:
    """Atomic read/write wrapper around the JSON checkpoint file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> CheckpointState:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return CheckpointState.from_dict(data)

    def save(self, state: CheckpointState, *, fsync: bool = False) -> None:
        """Atomically write ``state``. With ``fsync=True``, durably flush to disk."""
        tmp = self.path.with_name(self.path.name + ".tmp")
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            if fsync:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(tmp, self.path)
        if fsync:
            self._fsync_dir()

    def remove(self) -> None:
        """Delete the checkpoint (idempotent) — called on clean completion."""
        self.path.unlink(missing_ok=True)

    def _fsync_dir(self) -> None:
        directory = self.path.parent or Path(".")
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
        except OSError:  # pragma: no cover - platform without directory fds
            return
        try:
            os.fsync(dir_fd)
        except OSError:  # pragma: no cover - directory fsync unsupported (e.g. some FS)
            pass
        finally:
            os.close(dir_fd)


def describe_drift(state: CheckpointState, plan: SeedPlan) -> str:
    """Return a human-readable description of how ``state`` diverges from ``plan``.

    Used to build the abort message when ``plan_hash`` validation fails so the operator sees
    *what* changed rather than an opaque hash mismatch.
    """
    plan_tables = {t.name: t for t in plan.tables}
    state_names = list(state.tables)
    plan_names = [t.name for t in plan.tables]

    if state_names != plan_names:
        return f"table set/order changed: {state_names} -> {plan_names}"

    for name, progress in state.tables.items():
        planned = plan_tables[name]
        if progress.target != planned.target_count:
            return f"table {name!r} target changed: {progress.target} -> {planned.target_count}"
    return "plan structure changed (column or FK edges differ)"


def validate_resume(state: CheckpointState, plan: SeedPlan) -> None:
    """Raise :class:`PlanHashMismatchError` if ``state`` does not match ``plan``.

    Scenario: schema-drift on resume aborts cleanly — the seeder must refuse to write any rows
    against a checkpoint built for a different plan.
    """
    if state.plan_hash != plan.hash():
        raise PlanHashMismatchError(
            "cannot resume: " + describe_drift(state, plan) + "; "
            "remove the checkpoint to start a fresh run"
        )


__all__ = [
    "CheckpointState",
    "CheckpointStore",
    "PlanHashMismatchError",
    "TableProgress",
    "describe_drift",
    "validate_resume",
]
