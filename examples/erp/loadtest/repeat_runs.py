"""Aggregate repeated Locust runs and compare head against base to catch slowdowns.

A single short Locust run is too noisy to gate on. CI therefore runs base and head alternately
several times on one runner, aggregates each side into per-endpoint medians (with min/max
spread), and compares the medians with a relative tolerance. Pure stdlib, no ``locust`` import.

Only median p50/p95 latency (per endpoint and for the pooled Aggregated row), error rate, vanished
endpoints and request collapse gate. req/s and p99 are reported for information (see the README
for why).

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
DEFAULT_MIN_REQUESTS = 100  # pooled: total requests per side across all runs (~20 x 5 runs)
DEFAULT_MIN_RUNS = 3
DEFAULT_MIN_DELTA_MS = 20.0  # ignore latency rises smaller than this, whatever the ratio

_TABLE_HEADER = (
    "| Endpoint | runs b/h | req/s base | req/s head | req/s Δ | p50 base | p50 head | p50 Δ "
    "| p95 base | p95 head | p95 Δ | p99 base | p99 head | p99 Δ | err% | Status |"
)
_TABLE_RULE = "|---|---:|" + "---:|" * 13 + "---|"

METRICS = ("rps", "p50", "p95", "p99")
GATED_LATENCY = ("p50", "p95")


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
    min_run_requests: int = 0  # smallest per-run request count


@dataclass(frozen=True)
class Finding:
    name: str
    kind: str  # "p50", "p95", "error_rate", "missing", "requests" or "runs"
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
            min_run_requests=min(s.count for s in per_run),
        )
    return result


def dump_aggregate(path: Path, agg: dict[str, Aggregate]) -> None:
    payload = {
        name: {
            "runs": a.runs,
            "requests": a.requests,
            "min_run_requests": a.min_run_requests,
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
            min_run_requests=int(f.get("min_run_requests", int(f["requests"]) // int(f["runs"]))),
        )
        for name, f in data.items()
    }


def _status(bad: list[str], default: str) -> str:
    return "REGRESSED " + ", ".join(bad) if bad else default


def _max_runs(agg: dict[str, Aggregate]) -> int:
    return max((a.runs for a in agg.values()), default=0)


def _check_runs(
    base: dict[str, Aggregate],
    head: dict[str, Aggregate],
    min_runs: int,
    findings: list[Finding],
    notes: list[str],
) -> None:
    for side, agg in (("base", base), ("head", head)):
        runs = _max_runs(agg)
        if runs < min_runs:
            findings.append(Finding(side, "runs", runs, runs, min_runs))
            notes.append(f"{side}: only {runs} run(s), need {min_runs}")


def compare_aggregates(
    base: dict[str, Aggregate],
    head: dict[str, Aggregate],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE,
    min_requests: int = DEFAULT_MIN_REQUESTS,
    min_runs: int = DEFAULT_MIN_RUNS,
    min_delta_ms: float = DEFAULT_MIN_DELTA_MS,
) -> Comparison:
    """Flag errors, vanished endpoints and a rise in median p50/p95 beyond ``tolerance``.

    A latency rise only counts when it also exceeds ``min_delta_ms`` in absolute terms. The
    Aggregated row (every request pooled, the most stable signal) is gated like any endpoint.
    req/s and p99 are shown but never gate: with think time the load is closed-loop, so req/s
    barely moves, and p99 over a few hundred requests is a single slow request. ``min_requests``
    is the pooled total per side across all runs, so sparse single runs still count.
    """
    findings: list[Finding] = []
    notes: list[str] = []
    rows: list[tuple[str, Aggregate, Aggregate | None, str]] = []
    _check_runs(base, head, min_runs, findings, notes)
    for name in sorted(head):
        h = head[name]
        b = base.get(name)
        bad: list[str] = []
        if h.error_rate > max_error_rate:
            err_base = b.error_rate if b else 0.0
            findings.append(Finding(name, "error_rate", err_base, h.error_rate, max_error_rate))
            bad.append("errors")
        if b is None:
            notes.append(f"{name}: not in base, latency not compared")
            rows.append((name, h, None, _status(bad, "NEW")))
            continue
        if b.requests < min_requests:
            notes.append(
                f"{name}: skipped, too few pooled requests "
                f"(base {b.requests}, head {h.requests}; need {min_requests} per side)"
            )
            rows.append((name, h, b, _status(bad, "SKIPPED")))
            continue
        if h.requests < min_requests:
            findings.append(Finding(name, "requests", b.requests, h.requests, min_requests))
            bad.append("requests")
            rows.append((name, h, b, _status(bad, "")))
            continue
        for kind in GATED_LATENCY:
            bv = getattr(b, kind).median
            hv = getattr(h, kind).median
            if bv <= 0:
                notes.append(f"{name}: base {kind} is 0 (missing data), not compared")
                continue
            limit = bv * (1 + tolerance)
            if hv > limit and hv - bv > min_delta_ms:
                findings.append(Finding(name, kind, bv, hv, limit))
                bad.append(kind)
        rows.append((name, h, b, _status(bad, "OK")))
    for n in sorted(set(base) - set(head)):
        b = base[n]
        if b.requests >= min_requests:
            findings.append(Finding(n, "missing", b.requests, 0, min_requests))
        else:
            notes.append(f"{n}: in base but missing from head (base too sparse to gate)")
    return Comparison(findings, notes, rows)


def _delta(base: float, head: float) -> str:
    if base <= 0:
        return "n/a"
    return f"{(head - base) / base * 100:+.1f}%"


def _row_cells(h: Aggregate, b: Aggregate | None) -> list[str]:
    if b is None:
        return [f"-/{h.runs}", "-", f"{h.rps.median:.1f}", "-", "-", f"{h.p50.median:.0f}", "-",
                "-", f"{h.p95.median:.0f}", "-", "-", f"{h.p99.median:.0f}", "-"]  # fmt: skip
    cells = [f"{b.runs}/{h.runs}"]
    for m, fmt in (("rps", ".1f"), ("p50", ".0f"), ("p95", ".0f"), ("p99", ".0f")):
        bm, hm = getattr(b, m).median, getattr(h, m).median
        cells += [format(bm, fmt), format(hm, fmt), _delta(bm, hm)]
    return cells


def render_markdown(cmp: Comparison, *, tolerance: float) -> str:
    """Markdown table: median head vs base with relative change, plus notes and verdict."""
    lines = [
        f"### Load test regression gate (p50/p95 tolerance {tolerance * 100:.0f}%)",
        "",
        (
            "p50 and p95 gate, per endpoint and for the pooled Aggregated row; req/s and p99 are "
            "informational."
        ),
        "",
        _TABLE_HEADER,
        _TABLE_RULE,
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


def run_aggregate(stats: list[Path], out: Path, *, min_runs: int = 1) -> int:
    parsed = [parse_locust_stats(p.read_text(encoding="utf-8")) for p in stats if p.is_file()]
    runs = [r for r in parsed if r]
    if not runs:
        print("error: no endpoint rows parsed from the given stats files", file=sys.stderr)
        return 1
    if len(runs) < min_runs:
        print(f"error: only {len(runs)} usable run(s), need {min_runs}", file=sys.stderr)
        return 1
    dump_aggregate(out, aggregate_runs(runs))
    print(f"aggregated {len(runs)} run(s) -> {out}")
    return 0


@dataclass(frozen=True)
class Thresholds:
    tolerance: float = DEFAULT_TOLERANCE
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE
    min_requests: int = DEFAULT_MIN_REQUESTS
    min_runs: int = DEFAULT_MIN_RUNS
    min_delta_ms: float = DEFAULT_MIN_DELTA_MS


def run_compare(base: Path, head: Path, limits: Thresholds, report_path: Path | None = None) -> int:
    cmp = compare_aggregates(
        load_aggregate(base),
        load_aggregate(head),
        tolerance=limits.tolerance,
        max_error_rate=limits.max_error_rate,
        min_requests=limits.min_requests,
        min_runs=limits.min_runs,
        min_delta_ms=limits.min_delta_ms,
    )
    report = render_markdown(cmp, tolerance=limits.tolerance)
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
    agg.add_argument("--min-runs", type=int, default=1, help="fail below this many usable runs")
    cmp = sub.add_parser("compare", help="compare head aggregate against base aggregate")
    cmp.add_argument("--base", required=True, type=Path)
    cmp.add_argument("--head", required=True, type=Path)
    cmp.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    cmp.add_argument("--max-error-rate", type=float, default=DEFAULT_MAX_ERROR_RATE)
    cmp.add_argument(
        "--min-requests",
        type=int,
        default=DEFAULT_MIN_REQUESTS,
        help="minimum total requests per side, pooled over all runs",
    )
    cmp.add_argument("--min-runs", type=int, default=DEFAULT_MIN_RUNS)
    cmp.add_argument("--min-delta-ms", type=float, default=DEFAULT_MIN_DELTA_MS)
    cmp.add_argument("--report", type=Path, help="also write the markdown report to this file")
    args = parser.parse_args(argv)
    if args.command == "aggregate":
        return run_aggregate(args.stats, args.out, min_runs=args.min_runs)
    limits = Thresholds(
        tolerance=args.tolerance,
        max_error_rate=args.max_error_rate,
        min_requests=args.min_requests,
        min_runs=args.min_runs,
        min_delta_ms=args.min_delta_ms,
    )
    return run_compare(args.base, args.head, limits, report_path=args.report)
