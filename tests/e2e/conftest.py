from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing

import pytest


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
        "examples.simple_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(e2e_port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    base = f"http://127.0.0.1:{e2e_port}"

    try:
        # Wait for server readiness
        deadline = time.time() + 5
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/", timeout=0.5)
                if r.status_code == 200:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Server did not start: {last_err}")

        yield base
    finally:
        # stdout, stderr = proc.communicate()
        # print("\n--- Uvicorn stdout ---")
        # print(stdout)
        # print("--- Uvicorn stderr ---")
        # print(stderr)
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
