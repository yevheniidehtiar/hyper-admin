import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import closing
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

_IN_CONTAINER = os.environ.get("IS_SANDBOX") == "1"

# Server start is slower inside Docker or on a loaded machine (pre-push runs
# while other work is going on, and the xdist workers start several servers at
# once); a slow start must not fail the suite.
_SERVER_TIMEOUT = 30

# ``pytest -n auto`` worker count for this suite. Every worker drives its own
# Chromium plus one uvicorn per test, so the pool is sized for Playwright, not
# for the CPU count: four by default, ``E2E_WORKERS=<n>`` overrides it.
_DEFAULT_E2E_WORKERS = 4

# Header every test server stamps on all responses (uvicorn ``--header``) with
# this session's random token. Readiness only accepts a server that echoes it,
# so a foreign server on the port (another worktree's suite) is never used.
_TOKEN_HEADER = "X-E2E-Token"
_SPAWN_ATTEMPTS = 3
_SESSION_TOKEN = ""


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    """Size ``-n auto`` for the E2E suite (see ``_DEFAULT_E2E_WORKERS``)."""
    return int(os.environ.get("E2E_WORKERS") or _DEFAULT_E2E_WORKERS)


def csrf_headers(page: "Page") -> dict[str, str]:
    """Return the ``X-CSRF-Token`` header for the admin page open in ``page`` (SDD D.1).

    Pages rendered by an admin with CSRF enforced (any auth configured) carry the
    token in ``<meta name="csrf-token">``. ``page.request`` shares the browser
    context's cookies, so sending that token completes the double-submit pair,
    exactly as the page's own HTMX calls do.
    """
    token = page.locator('meta[name="csrf-token"]').get_attribute("content") or ""
    return {"X-CSRF-Token": token}


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Add Docker-safe Chromium flags when running inside a container."""
    if not _IN_CONTAINER:
        return browser_type_launch_args
    return {
        **browser_type_launch_args,
        "args": [
            *browser_type_launch_args.get("args", []),
            "--disable-dev-shm-usage",  # use /tmp instead of /dev/shm (Docker default is 64 MB)
            "--disable-gpu",
            "--disable-background-networking",  # avoid firewall-blocked Google service requests
        ],
    }


def _tail(log: Any, lines: int = 40) -> str:
    """Return the last ``lines`` lines a test server wrote to ``log``."""
    log.flush()
    log.seek(0)
    return "".join(log.readlines()[-lines:])


def _free_port() -> int:
    """Ask the OS for a free port (bind to 0) and return it.

    The OS hands out ephemeral ports system-wide, so concurrent processes and
    worktrees do not get the same one. The port is released before uvicorn binds
    it; ``_spawn_uvicorn`` covers that small window (retry + identity check).
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session", autouse=True)
def _e2e_token() -> str:
    """Random per-session identity token every test server must echo."""
    global _SESSION_TOKEN  # noqa: PLW0603
    _SESSION_TOKEN = uuid.uuid4().hex
    return _SESSION_TOKEN


@pytest.fixture
def e2e_port() -> int:
    """Provide a free localhost port, chosen by the OS, per test function."""
    return _free_port()


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            if os.name == "nt":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def _log_tail(log_path: str) -> str:
    with open(log_path) as log:
        return _tail(log)


def _probe(
    requests: Any, proc: subprocess.Popen, base: str, ready_path: str, log_path: str
) -> bool | None:
    """One readiness probe. True: ready. None: our server exited. False: not yet.

    Raises when something other than our own server answers on the port.
    """
    if proc.poll() is not None:
        return None
    try:
        r = requests.get(base + ready_path, timeout=0.5)
    except Exception:
        return False
    if r.headers.get(_TOKEN_HEADER) != _SESSION_TOKEN:
        try:  # our server may have lost the bind race: give it a moment to exit
            proc.wait(timeout=2)
            return None
        except subprocess.TimeoutExpired:
            pass
        _terminate(proc)
        raise RuntimeError(
            f"Foreign server on {base}: it does not echo this run's {_TOKEN_HEADER} "
            f"token, so it is not the test server this session started. Refusing to "
            f"use it.\n{_log_tail(log_path)}"
        )
    return r.status_code == HTTPStatus.OK


def _spawn_uvicorn(
    module_path: str,
    port: int | None = None,
    ready_path: str = "/admin/login",
    extra_env: dict[str, str] | None = None,
):
    """Spawn ``uvicorn module_path:app`` and block until it answers ``ready_path`` with 200.

    Readiness requires this session's identity header, so a foreign server is
    never mistaken for ours. If the port was taken in the gap between choosing
    and binding it, the server is respawned on a fresh OS-chosen port. Returns
    ``(proc, base_url)`` (the port may differ from the requested one).

    ``extra_env`` is merged over the inherited environment (e.g. to set a
    ``HYPERADMIN_*`` setting for one fixture app only).
    """
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"
    env.update(extra_env or {})
    for attempt in range(_SPAWN_ATTEMPTS):
        use_port = port if (port is not None and attempt == 0) else _free_port()
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            f"{module_path}:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(use_port),
            "--log-level",
            "warning",
            "--header",
            f"{_TOKEN_HEADER}:{_SESSION_TOKEN}",
        ]
        # Output goes to a temp file, not a PIPE: an unread pipe fills (~64 KB) and
        # blocks the server mid-run. The parent's handle closes; the child keeps its own.
        fd, log_path = tempfile.mkstemp(prefix="hyperadmin-e2e-", suffix=".log")
        with os.fdopen(fd, "w") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, text=True)

        base = f"http://localhost:{use_port}"
        deadline = time.time() + _SERVER_TIMEOUT
        while time.time() < deadline:
            state = _probe(requests, proc, base, ready_path, log_path)
            if state:
                return proc, base
            if state is None:
                break
            time.sleep(0.3)
        else:
            _terminate(proc)
            raise RuntimeError(
                f"Server {module_path} did not start within {_SERVER_TIMEOUT}s\n"
                f"{_log_tail(log_path)}"
            )
    raise RuntimeError(
        f"Server {module_path} could not bind a port in {_SPAWN_ATTEMPTS} attempts\n"
        f"{_log_tail(log_path)}"
    )


@pytest.fixture
def demo_base_url(e2e_port: int) -> Iterator[str]:
    """Start the demo_app (:mod:`examples.simple.main`) via uvicorn and yield the base URL."""
    proc, base = _spawn_uvicorn("examples.simple.main", e2e_port, ready_path="/")
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def mfa_base_url(e2e_port: int) -> Iterator[str]:
    """Start an MFA-enabled HyperAdmin app and yield the base URL.

    Seeds two superusers on startup:

    * ``alice / secret`` with ``mfa_enabled=True``
    * ``bob   / secret`` with ``mfa_enabled=False``

    Exposes ``/_test/latest_code?email=...`` and ``/_test/reset_otp_state``
    (wipes captured codes) on the host, and
    ``/admin/mfa/_test/backdate_session_otp`` inside the admin sub-app (it
    needs the admin session), for Playwright to drive the OTP flow
    deterministically.
    """
    proc, base = _spawn_uvicorn("tests.e2e._mfa_app", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def auth_base_url(e2e_port: int) -> Iterator[str]:
    """Start an auth-enabled HyperAdmin app and yield the base URL.

    The app seeds superuser ``alice / secret123`` on startup.
    Auth middleware redirects unauthenticated requests to ``/admin/login``.
    """
    proc, base = _spawn_uvicorn("tests.e2e._auth_app", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def realtime_base_url(e2e_port: int) -> Iterator[str]:
    """Start an auth + realtime HyperAdmin app and yield the base URL.

    Seeds ``alice / secret123`` and enables ``RealtimeSettings`` with a 1 s
    heartbeat so lifecycle assertions don't have to wait for the production
    default of 15 s.
    """
    proc, base = _spawn_uvicorn("tests.e2e._realtime_app", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def plugin_base_url(e2e_port: int) -> Iterator[str]:
    """Start the demo-plugin app (:mod:`tests.e2e.apps.plugin_registry`) and yield the base URL.

    Seeds superuser ``alice`` and permissionless ``bob`` (both ``secret123``).
    """
    proc, base = _spawn_uvicorn("tests.e2e.apps.plugin_registry", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def report_charts_base_url(e2e_port: int) -> Iterator[str]:
    """Start the chart-report app (:mod:`tests.e2e.apps.report_charts`) and yield the base URL."""
    proc, base = _spawn_uvicorn("tests.e2e.apps.report_charts", e2e_port, ready_path="/host")
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def bridge_base_url(e2e_port: int) -> Iterator[str]:
    """Start the bridge-mode app (:mod:`tests.e2e._bridge_app`) and yield the base URL.

    The host authenticates with a ``host_user=ada`` cookie; there is no admin login page.
    """
    proc, base = _spawn_uvicorn("tests.e2e._bridge_app", e2e_port, ready_path="/healthz")
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def restartable_realtime_url(e2e_port: int) -> Iterator[dict]:
    """Yield a controller for a realtime app that can be killed and restarted.

    Returned mapping: ``{"base": str, "kill": Callable[[], None],
    "start": Callable[[], None]}``. Tests use this fixture only for the
    "server restart triggers reconnect" scenario; the standard fixture above
    handles every other case.
    """
    state: dict = {"proc": None, "base": f"http://localhost:{e2e_port}"}

    def start() -> None:
        proc, base = _spawn_uvicorn("tests.e2e._realtime_app", e2e_port)
        state["proc"] = proc
        state["base"] = base

    def kill() -> None:
        if state["proc"] is not None:
            _terminate(state["proc"])
            state["proc"] = None

    start()
    try:
        yield {"base": state["base"], "kill": kill, "start": start, "state": state}
    finally:
        kill()


@pytest.fixture
def pk_types_base_url(e2e_port: int) -> Iterator[str]:
    """Start the pk-type and timezone fixture app and yield the base URL.

    Wires :mod:`tests.e2e.apps.pk_types` (UUID, natural ``str`` and ``int``
    primary keys plus a timezone-aware ``Event``) with
    ``HYPERADMIN_TIMEZONE=Europe/Amsterdam``. Each server gets a fresh
    temp-file SQLite database seeded with two Documents, Country ``FR`` and
    one Product.
    """
    proc, base = _spawn_uvicorn(
        "tests.e2e.apps.pk_types",
        e2e_port,
        ready_path="/",
        extra_env={"HYPERADMIN_TIMEZONE": "Europe/Amsterdam"},
    )
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def object_perm_base_url(e2e_port: int, tmp_path: Path) -> Iterator[str]:
    """Start an object-permission-enabled HyperAdmin app for E2E tests.

    Wires :mod:`tests.e2e._object_perm_app`, which seeds:
      * non-superuser ``bob`` (password ``secret123``) holding all model-level
        ``Order`` permissions — any 403 observed is therefore object-level.
      * superuser ``admin`` (password ``secret123``).
      * three ``Order`` rows (#10, #20 owned by bob; #40 owned by user 99).

    The configured object-permission checker denies non-superusers any
    interaction with order #40 (Order is the object-permission model). RLS
    is exercised via a separate ``Document`` model whose ``DocumentAdmin``
    overrides ``get_queryset`` to filter list/detail to
    ``request.state.user.id`` for non-superusers — keeping each enforcement
    layer isolated to its own model so a single scenario tests one rule.
    """
    # Each subprocess gets its own DB file (under the test's own tmp_path, so
    # parallel workers never share one) and tests never see stale data from a
    # previously-run server.
    proc, base = _spawn_uvicorn(
        "tests.e2e._object_perm_app",
        e2e_port,
        extra_env={"HYPERADMIN_E2E_OBJPERM_DB": str(tmp_path / "objperm.db")},
    )
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def bulk_base_url(e2e_port: int) -> Iterator[str]:
    """Start the bulk-action fixture app (:mod:`tests.e2e.apps.bulk_actions`) and yield the base URL.

    Auth is on (superuser ``alice / secret123``); ``Order`` rows 1, 2 and 3
    are seeded with the ``archive`` (formless), ``reassign`` (parameter
    form) and ``archive_overdue`` (no selection required) bulk actions. The
    host exposes ``/_test/calls``, ``/_test/reset``, ``/_test/forbid`` and
    ``/_test/deny`` so tests can observe and steer the handler.
    """
    proc, base = _spawn_uvicorn("tests.e2e.apps.bulk_actions", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def autocomplete_base_url(e2e_port: int) -> Iterator[str]:
    """Start the autocomplete fixture app (:mod:`tests.e2e.apps.autocomplete`) and yield the base URL.

    Auth is on (superuser ``alice / secret123``). ``Product`` has FKs to the
    registered ``Supplier`` (rendered as ``"{name} — {city}"``) and
    ``Variant`` (dependent on ``supplier_id``), and to the unregistered
    ``Brand``. Suppliers 42, 43 and 44, variants 1 and 2 and brand 1 are seeded.
    """
    proc, base = _spawn_uvicorn("tests.e2e.apps.autocomplete", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


@pytest.fixture
def start_server(e2e_port: int) -> Iterator[Callable[..., str]]:
    """Return ``start(module_path, ready_path=..., extra_env=...) -> base_url`` for ad-hoc apps.

    For test modules that own a fixture app: the server gets this session's
    identity token and is terminated at teardown.
    """
    procs: list[subprocess.Popen] = []

    def start(module_path: str, ready_path: str = "/admin/login", **kwargs: Any) -> str:
        proc, base = _spawn_uvicorn(module_path, e2e_port, ready_path=ready_path, **kwargs)
        procs.append(proc)
        return base

    try:
        yield start
    finally:
        for proc in procs:
            _terminate(proc)
