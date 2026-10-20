import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import closing
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

_IN_CONTAINER = os.environ.get("IS_SANDBOX") == "1"

# Server start is slower inside Docker or on a loaded machine (pre-push runs
# while other work is going on); a slow start must not fail the suite.
_SERVER_TIMEOUT = 30 if _IN_CONTAINER else 15


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


def _find_free_port() -> int:
    """Find an available TCP port on localhost.

    Returns
    -------
    int
        A free port number bound to 127.0.0.1.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


@pytest.fixture
def e2e_port() -> int:
    """Provide a free localhost port for the demo server per test function."""
    return _find_free_port()


@pytest.fixture
def demo_base_url(e2e_port: int) -> Iterator[str]:
    """Start the demo_app via uvicorn in a subprocess and yield base URL.

    This fixture gracefully skips if optional dependencies are missing
    and attempts a clean shutdown after the test.
    """
    # Optional dependencies: skip if missing
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "examples.simple.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(e2e_port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"

    # A temp file, not a PIPE: an unread pipe fills (~64 KB) and blocks the server mid-run.
    with tempfile.TemporaryFile(mode="w+") as server_log:
        proc = subprocess.Popen(
            cmd,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )

        base = f"http://localhost:{e2e_port}"

        try:
            # Wait for server readiness
            deadline = time.time() + _SERVER_TIMEOUT
            last_err: Exception | None = None
            while time.time() < deadline:
                try:
                    r = requests.get(base + "/", timeout=0.5)
                    if r.status_code == HTTPStatus.OK:
                        break
                except Exception as e:
                    last_err = e
                time.sleep(0.3)
            else:
                raise RuntimeError(f"Server did not start: {last_err}\n{_tail(server_log)}")

            yield base
        finally:
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
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "tests.e2e._mfa_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(e2e_port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,  # an unread PIPE fills (~64 KB) and blocks the server
        stderr=subprocess.DEVNULL,
        env=env,
        text=True,
    )

    base = f"http://localhost:{e2e_port}"

    try:
        deadline = time.time() + _SERVER_TIMEOUT
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/admin/login", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"MFA server did not start: {last_err}")

        yield base
    finally:
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


@pytest.fixture
def auth_base_url(e2e_port: int) -> Iterator[str]:
    """Start an auth-enabled HyperAdmin app and yield the base URL.

    The app seeds superuser ``alice / secret123`` on startup.
    Auth middleware redirects unauthenticated requests to ``/admin/login``.
    """
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "tests.e2e._auth_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(e2e_port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,  # an unread PIPE fills (~64 KB) and blocks the server
        stderr=subprocess.DEVNULL,
        env=env,
        text=True,
    )

    base = f"http://localhost:{e2e_port}"

    try:
        deadline = time.time() + _SERVER_TIMEOUT
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/admin/login", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Auth server did not start: {last_err}")

        yield base
    finally:
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


def _spawn_uvicorn(
    module_path: str,
    port: int,
    ready_path: str = "/admin/login",
    extra_env: dict[str, str] | None = None,
):
    """Spawn ``uvicorn module_path:app`` and block until ``ready_path`` returns 200.

    ``extra_env`` is merged over the inherited environment (e.g. to set a
    ``HYPERADMIN_*`` setting for one fixture app only).
    """
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        f"{module_path}:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    env = os.environ.copy()
    env["E2E_TESTING"] = "1"
    env.update(extra_env or {})
    # Output goes to a temp file, not a PIPE: an unread pipe fills (~64 KB) and
    # blocks the server mid-run. The parent's handle closes; the child keeps its own.
    fd, log_path = tempfile.mkstemp(prefix="hyperadmin-e2e-", suffix=".log")
    with os.fdopen(fd, "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, text=True)

    base = f"http://localhost:{port}"
    deadline = time.time() + _SERVER_TIMEOUT
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(base + ready_path, timeout=0.5)
            if r.status_code == HTTPStatus.OK:
                return proc, base
        except Exception as e:
            last_err = e
        time.sleep(0.3)
    proc.kill()
    with open(log_path) as log:
        raise RuntimeError(f"Server did not start: {last_err}\n{_tail(log)}")


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
def object_perm_base_url(e2e_port: int) -> Iterator[str]:
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
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "tests.e2e._object_perm_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(e2e_port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"
    # Each subprocess gets its own DB file so tests don't see stale data
    # from a previously-run server.
    env["HYPERADMIN_E2E_OBJPERM_DB"] = f"/tmp/hyperadmin-e2e-objperm-{e2e_port}.db"  # noqa: S108

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,  # an unread PIPE fills (~64 KB) and blocks the server
        stderr=subprocess.DEVNULL,
        env=env,
        text=True,
    )

    base = f"http://localhost:{e2e_port}"

    try:
        deadline = time.time() + _SERVER_TIMEOUT
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/admin/login", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Object-perm server did not start: {last_err}")

        yield base
    finally:
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
