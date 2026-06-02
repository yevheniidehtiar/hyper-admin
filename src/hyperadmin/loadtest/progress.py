"""Progress reporting for the bulk seeder.

Two reporters implement the :class:`ProgressReporter` protocol:

* :class:`RichReporter` — per-table progress bars with ETA and throughput, used on a TTY.
* :class:`PlainReporter` — one structured line per batch, used in CI / non-TTY logs.

``rich`` is soft-imported: if it is unavailable, or the output stream is not a TTY, or the
operator passed ``--no-progress``, the seeder falls back to :class:`PlainReporter`.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from rich.progress import TaskID


class ProgressReporter(Protocol):
    """Sink for per-table seeding progress."""

    def start_table(self, table: str, total: int) -> None: ...
    def advance(self, table: str, n: int) -> None: ...
    def finish_table(self, table: str) -> None: ...
    def close(self) -> None: ...


_RATE_K_THRESHOLD = 1000  # render rows/sec in thousands at or above this rate


def _format_rate(rows: int, elapsed: float) -> str:
    rate = rows / elapsed if elapsed > 0 else 0.0
    if rate >= _RATE_K_THRESHOLD:
        return f"{rate / _RATE_K_THRESHOLD:.1f}K/s"
    return f"{rate:.0f}/s"


class PlainReporter:
    """Emit one ``table=... completed=x/total rate=...`` line per advance."""

    def __init__(self, stream: TextIO | None = None, *, clock=time.monotonic) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._clock = clock
        self._totals: dict[str, int] = {}
        self._done: dict[str, int] = {}
        self._started_at: dict[str, float] = {}

    def start_table(self, table: str, total: int) -> None:
        self._totals[table] = total
        self._done[table] = 0
        self._started_at[table] = self._clock()

    def advance(self, table: str, n: int) -> None:
        self._done[table] = self._done.get(table, 0) + n
        started = self._started_at.get(table)
        elapsed = self._clock() - started if started is not None else 0.0
        rate = _format_rate(self._done[table], elapsed)
        print(
            f"table={table} completed={self._done[table]}/{self._totals.get(table, 0)} rate={rate}",
            file=self._stream,
            flush=True,
        )

    def finish_table(self, table: str) -> None:
        started = self._started_at.get(table)
        elapsed = self._clock() - started if started is not None else 0.0
        rate = _format_rate(self._done.get(table, 0), elapsed)
        print(
            f"table={table} done={self._done.get(table, 0)} elapsed={elapsed:.1f}s rate={rate}",
            file=self._stream,
            flush=True,
        )

    def close(self) -> None:
        """No-op: the plain reporter holds no resources."""


class RichReporter:
    """Per-table Rich progress bars. Constructed only when ``rich`` is importable."""

    def __init__(self) -> None:
        from rich.progress import (  # noqa: PLC0415 - soft dependency, imported on demand
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeRemainingColumn,
        )

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TextColumn("{task.fields[rate]}"),
        )
        self._tasks: dict[str, TaskID] = {}
        self._done: dict[str, int] = {}
        self._started_at: dict[str, float] = {}
        self._progress.start()

    def start_table(self, table: str, total: int) -> None:
        self._tasks[table] = self._progress.add_task(table, total=total, rate="")
        self._done[table] = 0
        self._started_at[table] = time.monotonic()

    def advance(self, table: str, n: int) -> None:
        self._done[table] += n
        elapsed = time.monotonic() - self._started_at[table]
        self._progress.update(
            self._tasks[table], advance=n, rate=_format_rate(self._done[table], elapsed)
        )

    def finish_table(self, table: str) -> None:  # noqa: ARG002 - protocol signature
        # Leave the completed bar visible; nothing else to do.
        self._progress.refresh()

    def close(self) -> None:
        self._progress.stop()


def make_reporter(*, no_progress: bool, stream: TextIO | None = None) -> ProgressReporter:
    """Pick the right reporter for the environment.

    Rich is used only on an interactive TTY when available and not disabled. Otherwise the
    plain reporter keeps CI logs readable.
    """
    out = stream if stream is not None else sys.stderr
    is_tty = bool(getattr(out, "isatty", lambda: False)())
    if no_progress or not is_tty:
        return PlainReporter(out)
    try:
        return RichReporter()
    except ImportError:  # pragma: no cover - rich is a dev dep; fallback path
        return PlainReporter(out)


__all__ = [
    "PlainReporter",
    "ProgressReporter",
    "RichReporter",
    "make_reporter",
]
