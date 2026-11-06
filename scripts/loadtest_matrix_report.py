"""Summarise a scripts/loadtest_matrix.sh run as a Markdown table.

Usage: python scripts/loadtest_matrix_report.py reports/loadtest-matrix

Reads each row's ``params`` file and the ``Aggregated`` line of its Locust ``*_stats.csv``,
then writes ``summary.md`` next to them and prints it.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

HEADER = (
    "| Row | DB | App CPUs | Users | Realtime | OK req/s | Median | p95 | p99 | Errors | 503s "
    "| Stopped early |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
)


def aggregated(stats_csv: Path) -> dict[str, str] | None:
    """Return the ``Aggregated`` row of a Locust stats CSV, or ``None`` when absent."""
    with stats_csv.open(newline="") as fh:
        for record in csv.DictReader(fh):
            if record["Name"] == "Aggregated":
                return record
    return None


def rejected(failures_csv: Path) -> int:
    """Count failures that are 503s: uvicorn's ``--limit-concurrency`` turning load away."""
    if not failures_csv.exists():
        return 0
    with failures_csv.open(newline="") as fh:
        return sum(int(r["Occurrences"]) for r in csv.DictReader(fh) if "503" in r["Error"])


def table_row(row_dir: Path) -> str:
    db, cpus, users, realtime, _run_time = row_dir.joinpath("params").read_text().split()
    stats = (
        aggregated(row_dir / "locust_stats.csv")
        if (row_dir / "locust_stats.csv").exists()
        else None
    )
    aborted = row_dir / "aborted"
    stopped = aborted.read_text().strip() if aborted.exists() else ""
    if stats is None:
        return f"| {row_dir.name} | {db} | {cpus} | {users} | {realtime} | failed | | | | | | {stopped} |\n"
    requests = int(stats["Request Count"]) or 1
    failures = int(stats["Failure Count"])
    # Successful requests only: a 503 costs the app almost nothing and would flatter throughput.
    ok_rps = float(stats["Requests/s"]) * (requests - failures) / requests
    return (
        f"| {row_dir.name} | {db} | {cpus} | {users} | {realtime} "
        f"| {ok_rps:.0f} | {stats['50%']} ms | {stats['95%']} ms "
        f"| {stats['99%']} ms | {failures / requests * 100:.2f}% "
        f"| {rejected(row_dir / 'locust_failures.csv') / requests * 100:.2f}% | {stopped} |\n"
    )


def main(out_dir: Path) -> None:
    def order(row_dir: Path) -> tuple[str, bool, int, int]:
        db, cpus, users, realtime, _run_time = row_dir.joinpath("params").read_text().split()
        return (db, realtime != "off", int(users), int(cpus))

    rows = sorted((p.parent for p in out_dir.glob("*/params")), key=order)
    summary = HEADER + "".join(table_row(row_dir) for row_dir in rows)
    out_dir.joinpath("summary.md").write_text(summary)
    sys.stdout.write(summary)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "reports/loadtest-matrix"))
