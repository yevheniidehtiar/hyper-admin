import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing
from http import HTTPStatus
from typing import Any

import pytest

_IN_CONTAINER = os.environ.get("IS_SANDBOX") == "1"

# Server start is slower inside Docker; give it more time.
_SERVER_TIMEOUT = 15 if _IN_CONTAINER else 5


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

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
            raise RuntimeError(f"Server did not start: {last_err}")

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

    Exposes ``/_test/latest_code?email=...``, ``/_test/reset_otp_state``,
    and ``/_test/backdate_session_otp`` for Playwright to drive the OTP
    flow deterministically.
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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


def _spawn_uvicorn(module_path: str, port: int, ready_path: str = "/admin/login"):
    """Spawn ``uvicorn module_path:app`` and block until ``ready_path`` returns 200."""
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
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)

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
    raise RuntimeError(f"Server did not start: {last_err}")


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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
