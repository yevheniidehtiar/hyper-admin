"""Typing regression check for the ``SessionFactory`` seam (st-v058-byoa-51).

``docs/guides/existing-app.md`` and ``examples/byoa`` pass a plain
``async_sessionmaker(engine)`` as ``Admin(session_factory=...)``. The
``AsyncSessionLike`` protocol must accept a real ``AsyncSession`` so a typed host
that follows the guide type-checks. Pre-commit runs mypy on ``src/`` only, so this
test runs mypy on a host-style snippet.
"""

from __future__ import annotations

from pathlib import Path

from mypy import api as mypy_api

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

HOST_SNIPPET = """
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hyperadmin.core.adapters import SessionFactory

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
factory: SessionFactory = async_sessionmaker(engine)
factory_no_expire: SessionFactory = async_sessionmaker(engine, expire_on_commit=False)
"""


def test_async_sessionmaker_type_checks_as_a_session_factory(tmp_path: Path) -> None:
    """
    Scenario: a host's async_sessionmaker type-checks as a SessionFactory
      Given a typed host module that builds async_sessionmaker(engine)
      When  mypy checks the assignment to hyperadmin's SessionFactory
      Then  mypy reports no errors
    """
    # Given a typed host module that builds async_sessionmaker(engine)
    args = [
        "--config-file",
        str(PYPROJECT),
        "--junit-xml",
        str(tmp_path / "mypy.xml"),
        "--cache-dir",
        str(tmp_path / ".mypy_cache"),
        "-c",
        HOST_SNIPPET,
    ]

    # When mypy checks the assignment to hyperadmin's SessionFactory
    stdout, stderr, status = mypy_api.run(args)

    # Then mypy reports no errors
    assert status == 0, stdout + stderr
