"""Runtime dependency audit (st-v058-byoa-11, SDD section E).

The installed distribution metadata is the same ``Requires-Dist`` list a built
wheel carries, so these tests check what a ``pip install hyper-admin`` pulls in.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import requires
from pathlib import Path

import pytest
from packaging.requirements import Requirement

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _runtime_requirements() -> list[Requirement]:
    """Return the distribution's requirements that are not tied to an extra."""
    parsed = [Requirement(raw) for raw in requires("hyper-admin") or []]
    return [req for req in parsed if req.marker is None or "extra" not in str(req.marker)]


def _runtime_names() -> set[str]:
    return {req.name.lower() for req in _runtime_requirements()}


def test_dev_only_packages_are_not_runtime_deps() -> None:
    """Scenario: dev-only packages are not runtime deps."""
    names = _runtime_names()

    assert "appnope" not in names
    assert "uvicorn" not in names
    assert "httpx" not in names
    assert "pydantic-settings" in names


def test_fastapi_is_required_without_the_standard_extra() -> None:
    fastapi = [req for req in _runtime_requirements() if req.name.lower() == "fastapi"]

    assert len(fastapi) == 1
    assert fastapi[0].extras == set()


def test_python_multipart_is_declared_once() -> None:
    multipart = [req for req in _runtime_requirements() if req.name.lower() == "python-multipart"]

    assert len(multipart) == 1


def test_demo_mode_and_timezone_dependencies_are_runtime() -> None:
    """Zero-config demo mode needs aiosqlite; zoneinfo needs tzdata on Windows."""
    by_name = {req.name.lower(): req for req in _runtime_requirements()}

    assert "aiosqlite" in by_name
    assert "tzdata" in by_name
    assert str(by_name["tzdata"].marker) == 'sys_platform == "win32"'


def test_pydantic_settings_lower_bound_includes_the_advisory_fix() -> None:
    """GHSA-4xgf-cpjx-pc3j is fixed in pydantic-settings 2.14.2."""
    (req,) = [r for r in _runtime_requirements() if r.name.lower() == "pydantic-settings"]

    assert req.specifier.contains("2.14.2")
    assert not req.specifier.contains("2.14.1")


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required to build the wheel")
def test_built_wheel_imports_cleanly(tmp_path: Path) -> None:
    """Scenario: built wheel imports cleanly (fresh venv, no dev dependencies)."""
    uv = shutil.which("uv")
    assert uv is not None
    dist = tmp_path / "dist"
    venv = tmp_path / "venv"
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(dist), str(_REPO_ROOT)],
        check=True,
        capture_output=True,
        env=env,
    )
    (wheel,) = dist.glob("hyper_admin-*.whl")
    subprocess.run(
        [uv, "venv", "--python", sys.executable, str(venv)],
        check=True,
        capture_output=True,
        env=env,
    )
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), str(wheel)],
        check=True,
        capture_output=True,
        env=env,
    )

    result = subprocess.run(
        [str(python), "-c", "from hyperadmin import Admin; print(Admin.__name__)"],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Admin"


def test_pydantic_lower_bound_resolves_admin_forward_references() -> None:
    """pydantic < 2.10 cannot resolve the ``InlineModelSpec`` forward reference.

    With pydantic 2.7-2.9 registering admin routes fails with
    ``PydanticUndefinedAnnotation: name 'InlineModelSpec' is not defined``, so
    every declared pydantic floor must exclude those versions (and 2.10.0).
    """
    pydantic = [r for r in _runtime_requirements() if r.name.lower() == "pydantic"]

    assert pydantic
    for req in pydantic:
        assert not req.specifier.contains("2.9.2"), str(req)
        # 2.10.0 regressed default factories (fixed in 2.10.1); sqlmodel defaults break.
        assert not req.specifier.contains("2.10.0"), str(req)
        assert req.specifier.contains("2.11.7"), str(req)


def test_sqlalchemy_floor_on_python_313_is_importable() -> None:
    """SQLAlchemy < 2.0.31 fails to import on Python 3.13 (TypingOnly assertion)."""
    sqlalchemy = [r for r in _runtime_requirements() if r.name.lower() == "sqlalchemy"]
    py313 = [
        r for r in sqlalchemy if r.marker is None or r.marker.evaluate({"python_version": "3.13"})
    ]

    assert py313
    for req in py313:
        assert not req.specifier.contains("2.0.30"), str(req)


def test_sqlalchemy_floor_stops_aiosqlite_worker_threads() -> None:
    """aiosqlite>=0.22 workers are non-daemon; SQLAlchemy < 2.0.46 hangs the process on exit."""
    sqlalchemy = [r for r in _runtime_requirements() if r.name.lower() == "sqlalchemy"]

    assert sqlalchemy
    for req in sqlalchemy:
        assert not req.specifier.contains("2.0.45"), str(req)
        assert req.specifier.contains("2.0.46"), str(req)
