"""Aggregate repeated Locust runs and compare head against base to catch slowdowns.

A single short Locust run is too noisy to gate on. CI therefore runs base and head alternately
several times on one runner, aggregates each side into per-endpoint medians (with min/max
spread), and compares the medians with a relative tolerance. Pure stdlib, no ``locust`` import.

Reached through ``python -m examples.erp.loadtest.baselines aggregate|compare``.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from examples.erp.loadtest.baselines import EndpointStats, parse_locust_stats

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_TOLERANCE = 0.15
DEFAULT_MAX_ERROR_RATE = 0.01
DEFAULT_MIN_REQUESTS = 100

_TABLE_HEADER = (
    "| Endpoint | req/s base | req/s head | req/s Δ | p95 base | p95 head | p95 Δ "
    "| p99 base | p99 head | p99 Δ | err% | Status |"
)

METRICS = ("rps", "p50", "p95", "p99")


@dataclass(frozen=True)
class Spread:
    median: float
    low: float
    high: float


@dataclass(frozen=True)
class Aggregate:
    """Cross-run summary of one endpoint."""

    name: str
    runs: int
    requests: int  # total across runs
    error_rate: float  # pooled: total failures / total requests
    rps: Spread
    p50: Spread
    p95: Spread
    p99: Spread


@dataclass(frozen=True)
class Finding:
    name: str
    kind: str  # "rps", "p95", "p99" or "error_rate"
    base: float
    head: float
    limit: float


@dataclass(frozen=True)
class Comparison:
    findings: list[Finding]
    notes: list[str]
    rows: list[tuple[str, Aggregate, Aggregate | None, str]]


def _spread(values: Sequence[float]) -> Spread:
    return Spread(statistics.median(values), min(values), max(values))


def aggregate_runs(runs: Sequence[dict[str, EndpointStats]]) -> dict[str, Aggregate]:
    """Fold N parsed runs into ``{endpoint: Aggregate}`` (endpoints absent from a run skip it)."""
    names = sorted({name for run in runs for name in run})
    result: dict[str, Aggregate] = {}
    for name in names:
        per_run = [run[name] for run in runs if name in run]
        requests = sum(s.count for s in per_run)
        failures = sum(s.count * s.error_rate for s in per_run)
        result[name] = Aggregate(
            name=name,
            runs=len(per_run),
            requests=requests,
            error_rate=failures / requests if requests else 0.0,
            rps=_spread([s.throughput for s in per_run]),
            p50=_spread([s.p50 for s in per_run]),
            p95=_spread([s.p95 for s in per_run]),
            p99=_spread([s.p99 for s in per_run]),
        )
    return result


def dump_aggregate(path: Path, agg: dict[str, Aggregate]) -> None:
    payload = {
        name: {
            "runs": a.runs,
            "requests": a.requests,
            "error_rate": a.error_rate,
            **{m: vars(getattr(a, m)) for m in METRICS},
        }
        for name, a in agg.items()
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_aggregate(path: Path) -> dict[str, Aggregate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: Aggregate(
            name=name,
            runs=int(f["runs"]),
            requests=int(f["requests"]),
            error_rate=float(f["error_rate"]),
            rps=Spread(**f["rps"]),
            p50=Spread(**f["p50"]),
            p95=Spread(**f["p95"]),
            p99=Spread(**f["p99"]),
        )
        for name, f in data.items()
    }


def _regressed(bad: list[str]) -> str:
    return "REGRESSED " + ", ".join(bad)


def compare_aggregates(
    base: dict[str, Aggregate],
    head: dict[str, Aggregate],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE,
    min_requests: int = DEFAULT_MIN_REQUESTS,
) -> Comparison:
    """Flag a drop in median req/s or a rise in median p95/p99 beyond ``tolerance``."""
    findings: list[Finding] = []
    notes: list[str] = []
    rows: list[tuple[str, Aggregate, Aggregate | None, str]] = []
    for name in sorted(head):
        h = head[name]
        b = base.get(name)
        bad: list[str] = []
        if h.error_rate > max_error_rate:
            findings.append(
                Finding(
                    name, "error_rate", b.error_rate if b else 0.0, h.error_rate, max_error_rate
                )
            )
            bad.append("errors")
        if b is None:
            notes.append(f"{name}: not in base, throughput/latency not compared")
            rows.append((name, h, None, _regressed(bad) if bad else "NEW"))
            continue
        if min(b.requests, h.requests) < min_requests:
            notes.append(
                f"{name}: skipped, too few requests (base {b.requests}, head {h.requests}, "
                f"need {min_requests})"
            )
            rows.append((name, h, b, _regressed(bad) if bad else "SKIPPED"))
            continue
        if b.rps.median > 0 and h.rps.median < b.rps.median * (1 - tolerance):
            limit = b.rps.median * (1 - tolerance)
            findings.append(Finding(name, "rps", b.rps.median, h.rps.median, limit))
            bad.append("req/s")
        for kind in ("p95", "p99"):
            bv = getattr(b, kind).median
            hv = getattr(h, kind).median
            if bv > 0 and hv > bv * (1 + tolerance):
                findings.append(Finding(name, kind, bv, hv, bv * (1 + tolerance)))
                bad.append(kind)
        rows.append((name, h, b, _regressed(bad) if bad else "OK"))
    notes.extend(f"{n}: in base but missing from head" for n in sorted(set(base) - set(head)))
    return Comparison(findings, notes, rows)


def _delta(base: float, head: float) -> str:
    if base <= 0:
        return "n/a"
    return f"{(head - base) / base * 100:+.1f}%"


def _row_cells(h: Aggregate, b: Aggregate | None) -> list[str]:
    if b is None:
        return ["—", f"{h.rps.median:.1f}", "n/a", "—", f"{h.p95.median:.0f}", "n/a", "—",
                f"{h.p99.median:.0f}", "n/a"]  # fmt: skip
    return [
        f"{b.rps.median:.1f}", f"{h.rps.median:.1f}", _delta(b.rps.median, h.rps.median),
        f"{b.p95.median:.0f}", f"{h.p95.median:.0f}", _delta(b.p95.median, h.p95.median),
        f"{b.p99.median:.0f}", f"{h.p99.median:.0f}", _delta(b.p99.median, h.p99.median),
    ]  # fmt: skip


def render_markdown(cmp: Comparison, *, tolerance: float) -> str:
    """Markdown table: median head vs base with relative change, plus notes and verdict."""
    lines = [
        f"### Load test regression gate (tolerance {tolerance * 100:.0f}%)",
        "",
        _TABLE_HEADER,
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, h, b, status in cmp.rows:
        cells = " | ".join(_row_cells(h, b))
        lines.append(f"| `{name}` | {cells} | {h.error_rate * 100:.2f} | {status} |")
    if cmp.notes:
        lines += ["", "Notes:", *[f"- {n}" for n in cmp.notes]]
    lines.append("")
    if cmp.findings:
        lines.append(f"**FAILED**: {len(cmp.findings)} regression(s):")
        for f in cmp.findings:
            lines.append(
                f"- `{f.name}`: {f.kind} base {f.base:.3f} -> head {f.head:.3f} (limit {f.limit:.3f})"
            )
    else:
        lines.append("**PASSED**: no regressions.")
    return "\n".join(lines) + "\n"


def run_aggregate(stats: list[Path], out: Path) -> int:
    parsed = [parse_locust_stats(p.read_text(encoding="utf-8")) for p in stats]
    runs = [r for r in parsed if r]
    if not runs:
        print("error: no endpoint rows parsed from the given stats files", file=sys.stderr)
        return 1
    dump_aggregate(out, aggregate_runs(runs))
    print(f"aggregated {len(runs)} run(s) -> {out}")
    return 0


def run_compare(
    base: Path,
    head: Path,
    *,
    tolerance: float,
    max_error_rate: float,
    min_requests: int,
    report_path: Path | None = None,
) -> int:
    cmp = compare_aggregates(
        load_aggregate(base),
        load_aggregate(head),
        tolerance=tolerance,
        max_error_rate=max_error_rate,
        min_requests=min_requests,
    )
    report = render_markdown(cmp, tolerance=tolerance)
    print(report)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    return 1 if cmp.findings else 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="baselines", description="Repeated-run regression gate.")
    sub = parser.add_subparsers(dest="command", required=True)
    agg = sub.add_parser("aggregate", help="fold N *_stats.csv files into per-endpoint medians")
    agg.add_argument("--stats", required=True, nargs="+", type=Path)
    agg.add_argument("--out", required=True, type=Path)
    cmp = sub.add_parser("compare", help="compare head aggregate against base aggregate")
    cmp.add_argument("--base", required=True, type=Path)
    cmp.add_argument("--head", required=True, type=Path)
    cmp.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    cmp.add_argument("--max-error-rate", type=float, default=DEFAULT_MAX_ERROR_RATE)
    cmp.add_argument("--min-requests", type=int, default=DEFAULT_MIN_REQUESTS)
    cmp.add_argument("--report", type=Path, help="also write the markdown report to this file")
    args = parser.parse_args(argv)
    if args.command == "aggregate":
        return run_aggregate(args.stats, args.out)
    return run_compare(
        args.base,
        args.head,
        tolerance=args.tolerance,
        max_error_rate=args.max_error_rate,
        min_requests=args.min_requests,
        report_path=args.report,
    )
