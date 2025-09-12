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
from pathlib import Path

import pytest
import requests
from playwright.sync_api import Page, expect


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


@pytest.fixture
def override_app_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)

        # Create templates directory
        templates_dir = app_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / "my_app").mkdir()
        (templates_dir / "my_app" / "mymodel").mkdir()
        (templates_dir / "my_app" / "mymodel" / "list.html").write_text("<h1>Overridden List Page</h1>")

        # Create main app file
        (app_dir / "main.py").write_text("""
from pathlib import Path
from fastapi import FastAPI
from hyperadmin import Admin

app = FastAPI()
templates_dir = Path(__file__).parent / "templates"
admin = Admin(app, discover_apps=['my_app'], template_dirs=[str(templates_dir)])
admin.mount(path="/admin")
""")

        # Create app with models
        (app_dir / "my_app").mkdir(exist_ok=True)
        (app_dir / "my_app" / "__init__.py").touch()
        (app_dir / "my_app" / "models.py").write_text("""
from sqlmodel import Field, SQLModel

class MyModel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
""")
        (app_dir / "my_app" / "admin.py").write_text("""
from hyperadmin.views import ModelView
from .models import MyModel

class MyModelAdmin(ModelView, model=MyModel):
    pass
""")
        yield app_dir


@pytest.fixture
def override_base_url(override_app_dir: Path) -> Iterator[str]:
    """Start the demo_app via uvicorn in a subprocess and yield base URL."""
    port = _find_free_port()

    # Add the app dir to the python path
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"/app/src{os.pathsep}{override_app_dir}{os.pathsep}{pythonpath}"
    print(f"PYTHONPATH: {env['PYTHONPATH']}")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=override_app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    base = f"http://127.0.0.1:{port}"

    try:
        # Wait for server readiness
        deadline = time.time() + 10
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/admin/mymodel", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            stdout, stderr = proc.communicate()
            print("--- Uvicorn stdout ---")
            print(stdout)
            print("--- Uvicorn stderr ---")
            print(stderr)
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


def test_template_override(page: Page, override_base_url: str):
    page.goto(override_base_url + "/admin/mymodel")
    expect(page.get_by_text("Overridden List Page")).to_be_visible()
