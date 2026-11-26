"""Load-test the 1.2-million-row scalability app on SQLite, PostgreSQL and PostgreSQL + trigram.

Each configuration seeds the same rows (``tests.e2e.apps.scalability_models`` at
``--scale``, 100 gives 1,200,605 rows), starts ``tests.e2e.apps.scalability`` with one
uvicorn worker and SQLAlchemy's default pool, and measures reads (list, detail, search) and
writes (create, update, delete) separately with ``scripts/loadtest_scale_locust.py``::

    uv sync --all-extras
    uv run python scripts/loadtest_scale.py                       # all three configurations
    uv run python scripts/loadtest_scale.py --configs sqlite      # one of them

Configurations:

* ``sqlite``: a SQLite file.
* ``postgres``: PostgreSQL 17 in Docker (``docker run postgres:17`` on a free local port,
  removed again when the script ends).
* ``postgres-trgm``: the same database plus a ``pg_trgm`` GIN index on the searched column
  (``e2e_sc_product.sku``), so the ``ILIKE '%term%'`` search can use an index.

The numbers are only worth something on an idle machine: before every Locust run the script
waits until the 1-minute load average is below ``--max-load`` (2.0) and CPU idle above
``--min-idle`` (85%), held for ``--hold`` seconds, and gives up after ``--quiet-wait``
seconds, printing the busiest processes. Each measurement runs ``--repeats`` times (2) and
the last run counts: the first warms the caches. Results land in ``--out``
(``reports/loadtest-scale/``): one JSON file per run and ``summary.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONFIGS = ("sqlite", "postgres", "postgres-trgm")
PG_IMAGE = "postgres:17"
PG_AUTH = "hyperadmin:hyperadmin"
PG_DB = "scale"
TRGM_INDEX = (
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    (
        "CREATE INDEX IF NOT EXISTS ix_e2e_sc_product_sku_trgm "
        "ON e2e_sc_product USING gin (sku gin_trgm_ops)"
    ),
    "ANALYZE e2e_sc_product",
)
MEASUREMENTS = {"reads": "ReadUser", "writes": "WriteUser"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _log(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


# -- idle gate -----------------------------------------------------------------------------


def _cpu_idle() -> float | None:
    """CPU idle percent over the next two seconds (macOS ``top``, Linux ``/proc/stat``)."""
    if sys.platform == "darwin":
        out = subprocess.run(
            ["/usr/bin/top", "-l", "2", "-n", "0", "-s", "2"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        found = re.findall(r"([\d.]+)% idle", out)
        return float(found[-1]) if found else None
    stat = Path("/proc/stat")
    if not stat.exists():
        return None
    before = [int(x) for x in stat.read_text().split()[1:8]]
    time.sleep(2)
    after = [int(x) for x in stat.read_text().split()[1:8]]
    delta = [b - a for a, b in zip(before, after, strict=True)]
    return 100 * (delta[3] + delta[4]) / max(sum(delta), 1)


def _host_sample() -> dict[str, float | None]:
    return {"load": os.getloadavg()[0], "idle": _cpu_idle()}


def _quiet(sample: dict[str, float | None], args: argparse.Namespace) -> bool:
    load, idle = sample["load"] or 0.0, sample["idle"]
    return load < args.max_load and (idle is None or idle > args.min_idle)


def _wait_for_quiet(args: argparse.Namespace) -> None:
    """Block until the host has been quiet for ``--hold`` seconds, or stop the script."""
    deadline = time.monotonic() + args.quiet_wait
    since: float | None = None
    while True:
        sample = _host_sample()
        now = time.monotonic()
        _log(f"   host load {sample['load']:.2f}, idle {sample['idle']}%")
        since = (since or now) if _quiet(sample, args) else None
        if since is not None and now - since >= args.hold:
            return
        if now > deadline:
            top = subprocess.run(
                ["/bin/ps", "-Ao", "pcpu,comm", "-r"], capture_output=True, text=True, check=False
            ).stdout.splitlines()[:12]
            raise SystemExit("host never got quiet; busiest processes:\n" + "\n".join(top))
        time.sleep(15)


# -- databases -----------------------------------------------------------------------------


class Postgres:
    """A throwaway ``postgres:17`` container on a free local port."""

    def __init__(self) -> None:
        if shutil.which("docker") is None:
            raise SystemExit("docker is not on PATH: the PostgreSQL rows need it")
        self.name = f"hyperadmin-loadtest-scale-{os.getpid()}"
        self.port = _free_port()
        user, password = PG_AUTH.split(":")
        subprocess.run(  # noqa: S603 - fixed argv
            [
                *("docker", "run", "-d", "--rm", "--name", self.name),
                *("-e", f"POSTGRES_USER={user}", "-e", f"POSTGRES_PASSWORD={password}"),
                *("-e", f"POSTGRES_DB={PG_DB}", "-p", f"127.0.0.1:{self.port}:5432"),
                PG_IMAGE,
                *("-c", "shared_buffers=256MB", "-c", "work_mem=16MB"),
                *("-c", "effective_cache_size=1GB", "-c", "max_connections=200"),
            ],
            check=True,
            capture_output=True,
        )
        for _ in range(120):
            ready = subprocess.run(  # noqa: S603 - fixed argv
                ["docker", "exec", self.name, "pg_isready", "-U", user, "-d", PG_DB],
                capture_output=True,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            self.stop()
            raise SystemExit("PostgreSQL did not become ready")
        time.sleep(2)  # the image restarts the server once after its init scripts

    def url(self, driver: str) -> str:
        return f"postgresql+{driver}://{PG_AUTH}@127.0.0.1:{self.port}/{PG_DB}"

    def execute(self, *statements: str) -> None:
        from sqlalchemy import create_engine, text  # noqa: PLC0415

        engine = create_engine(self.url("psycopg"), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                for statement in statements:
                    conn.execute(text(statement))
        finally:
            engine.dispose()

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True, check=False)  # noqa: S603


def _seed(url: str, state: Path, scale: int) -> tuple[int, float]:
    from tests.e2e.apps.scalability_models import seed_url  # noqa: PLC0415

    state.unlink(missing_ok=True)
    started = time.perf_counter()
    rows = seed_url(url, state, scale)
    return rows, time.perf_counter() - started


# -- app and Locust ------------------------------------------------------------------------


@contextlib.contextmanager
def _app(env: dict[str, str], log: Path) -> Any:
    port = _free_port()
    with log.open("w") as out:
        proc = subprocess.Popen(  # noqa: S603 - fixed argv
            [
                sys.executable,
                *("-m", "uvicorn", "tests.e2e.apps.scalability:app"),
                *("--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"),
            ],
            cwd=ROOT,
            env={**os.environ, "E2E_TESTING": "1", **env},
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            with (
                contextlib.suppress(OSError),
                urllib.request.urlopen(base + "/admin/login", timeout=2) as resp,  # noqa: S310
            ):
                if resp.status == 200:
                    break
            if proc.poll() is not None:
                raise SystemExit(f"app exited, see {log}")
            time.sleep(1)
        else:
            raise SystemExit(f"app did not come up, see {log}")
        yield base
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
        if proc.poll() is None:
            proc.kill()


def _locust(base: str, user_class: str, out: Path, args: argparse.Namespace) -> dict[str, Any]:
    locust = shutil.which("locust")
    if locust is None:
        raise SystemExit("locust is not installed: uv sync --extra loadtest")
    out.unlink(missing_ok=True)
    # An idle Mac can sleep mid-run: the clock stops and the run measures nothing.
    awake = ["/usr/bin/caffeinate", "-i"] if Path("/usr/bin/caffeinate").exists() else []
    run = subprocess.run(  # noqa: S603 - fixed argv
        [
            *awake,
            locust,
            *("-f", "scripts/loadtest_scale_locust.py", "--headless", "--only-summary"),
            *("-u", str(args.users), "-r", str(args.users), "-t", f"{int(args.seconds) + 120}s"),
            *("--host", base, user_class),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "LOADTEST_USER": "alice",
            "LOADTEST_PASSWORD": "secret123",
            "E2E_SCALABILITY_SCALE": str(args.scale),
            "SCALE_USERS": str(args.users),
            "SCALE_SECONDS": str(args.seconds),
            "SCALE_OUT": str(out),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if not out.exists():
        raise RuntimeError(f"locust {user_class} failed:\n{run.stderr[-2000:]}")
    figures: dict[str, Any] = json.loads(out.read_text())
    return figures


def _measure(config: str, base: str, args: argparse.Namespace) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for measurement, user_class in MEASUREMENTS.items():
        for i in range(args.repeats):
            if args.idle_gate:
                _wait_for_quiet(args)
            start = _host_sample()
            figures = _locust(
                base, user_class, args.out / f"{config}-{measurement}-{i + 1}.json", args
            )
            figures["host"] = {"start": start, "end": _host_sample()}
            total = figures["total"]
            _log(
                f"   {config} {measurement} run {i + 1}: {total['rps']:.0f} req/s, "
                f"median {total['p50']:.0f} ms, p95 {total['p95']:.0f} ms"
            )
            results[measurement] = figures  # the last run counts
    return results


# -- report --------------------------------------------------------------------------------

_ORDER = ("list", "detail", "search", "list+detail", "create", "update", "delete")


def _summary(all_results: dict[str, dict[str, Any]], facts: dict[str, Any]) -> str:
    lines = [
        (
            f"{facts['rows']:,} rows, {facts['users']} users, {facts['seconds']:.0f} s per "
            f"measurement, last of {facts['repeats']} runs, one uvicorn worker, Locust on the "
            f"same host ({facts['machine']})."
        ),
        "",
        "| Config | Endpoint | Requests | Fails | req/s | Median | p95 | p99 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for config, results in all_results.items():
        for measurement, figures in results.items():
            endpoints = figures["endpoints"]
            rows = [(n, endpoints[n]) for n in _ORDER if n in endpoints]
            rows.append((f"all {measurement}", figures["total"]))
            for name, row in rows:
                lines.append(
                    f"| {config} | {name} | {row['requests']} | {row['failures']} | "
                    f"{row['rps']:.1f} | {row['p50']:.0f} ms | {row['p95']:.0f} ms | "
                    f"{row['p99']:.0f} ms |"
                )
    return "\n".join(lines) + "\n"


def _machine() -> str:
    try:
        chip = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        chip = sys.platform
    return f"{chip}, {os.cpu_count()} CPUs"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--configs", default=",".join(CONFIGS), help="comma-separated")
    parser.add_argument("--scale", type=int, default=100, help="100 gives 1.2 M rows")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "loadtest-scale")
    parser.add_argument("--max-load", type=float, default=2.0)
    parser.add_argument("--min-idle", type=float, default=85.0)
    parser.add_argument("--hold", type=float, default=60.0)
    parser.add_argument("--quiet-wait", type=float, default=25 * 60.0)
    parser.add_argument(
        "--no-idle-gate",
        dest="idle_gate",
        action="store_false",
        help="run on a busy host anyway (the numbers are then not comparable)",
    )
    args = parser.parse_args(argv)
    configs = [c for c in args.configs.split(",") if c]
    unknown = set(configs) - set(CONFIGS)
    if unknown:
        parser.error(f"unknown configs: {', '.join(sorted(unknown))}")
    args.out.mkdir(parents=True, exist_ok=True)
    facts: dict[str, Any] = {
        "users": args.users,
        "seconds": args.seconds,
        "repeats": args.repeats,
        "machine": _machine(),
        "idle_gate": args.idle_gate,
    }
    results: dict[str, dict[str, Any]] = {}
    pg: Postgres | None = None
    # SIGTERM unwinds like Ctrl-C, so the app stops and the container is removed.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        if "sqlite" in configs:
            db = args.out / "scale.db"
            db.unlink(missing_ok=True)
            facts["rows"], seconds = _seed(
                f"sqlite:///{db}", db.with_suffix(".seed.json"), args.scale
            )
            _log(f"== sqlite: seeded {facts['rows']:,} rows in {seconds:.0f} s")
            with _app({"E2E_SCALABILITY_DB": str(db)}, args.out / "app-sqlite.log") as base:
                results["sqlite"] = _measure("sqlite", base, args)
        pg_configs = [c for c in configs if c.startswith("postgres")]
        if pg_configs:
            pg = Postgres()
            facts["rows"], seconds = _seed(pg.url("psycopg"), args.out / "pg.seed.json", args.scale)
            pg.execute("ANALYZE")
            _log(f"== postgres: seeded {facts['rows']:,} rows in {seconds:.0f} s")
            for config in ("postgres", "postgres-trgm"):  # the index is added, never dropped
                if config not in pg_configs:
                    continue
                if config == "postgres-trgm":
                    pg.execute(*TRGM_INDEX)
                env = {"E2E_SCALABILITY_DATABASE_URL": pg.url("asyncpg")}
                with _app(env, args.out / f"app-{config}.log") as base:
                    results[config] = _measure(config, base, args)
    finally:
        if pg is not None:
            pg.stop()
        (args.out / "results.json").write_text(
            json.dumps({"facts": facts, "results": results}, indent=2)
        )
    summary = _summary(results, facts)
    (args.out / "summary.md").write_text(summary)
    _log("\n" + summary)


if __name__ == "__main__":
    main()
