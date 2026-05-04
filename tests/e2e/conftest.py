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


@pytest.fixture
def object_perm_base_url(e2e_port: int) -> Iterator[str]:
    """Start an object-permission-enabled HyperAdmin app for E2E tests.

    Wires :mod:`tests.e2e._object_perm_app`, which seeds:
      * non-superuser ``bob`` (password ``secret123``) holding all model-level
        ``Order`` permissions — any 403 observed is therefore object-level.
      * superuser ``admin`` (password ``secret123``).
      * three ``Order`` rows (#10, #20 owned by bob; #40 owned by user 99).

    The configured object-permission checker denies non-superusers any
    interaction with order #40, while ``OrderAdmin.get_queryset`` filters
    list/detail to ``request.state.user.id`` for non-superusers.
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
