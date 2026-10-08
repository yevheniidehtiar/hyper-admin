"""Lazy ``hyperadmin.auth`` exports and ``auth.metadata()`` (st-v058-byoa-17, SDD B.5).

Table registration is process-global (``SQLModel.metadata``), so every scenario
runs in a fresh interpreter.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest


def _run(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _hyperadmin_tables_after(statement: str) -> str:
    return _run(
        f"""
        {statement}
        from sqlmodel import SQLModel
        print(sorted(t for t in SQLModel.metadata.tables if t.startswith("hyperadmin_")))
        """
    )


@pytest.mark.parametrize(
    "statement",
    [
        "import hyperadmin.auth.middleware",
        "import hyperadmin.auth",
        "from hyperadmin.auth import hash_password",
        "import hyperadmin",
    ],
)
def test_importing_auth_submodules_registers_no_tables(statement: str) -> None:
    """Scenario: importing auth submodules registers no tables."""
    assert _hyperadmin_tables_after(statement) == "[]"


def test_back_compat_import_returns_the_built_in_user_model() -> None:
    """Scenario: back-compat import."""
    out = _run(
        """
        from hyperadmin.auth import User
        import hyperadmin.auth.models as models
        print(User is models.User, User.__tablename__)
        """
    )
    assert out == "True hyperadmin_users"


def test_all_legacy_exports_resolve() -> None:
    out = _run(
        """
        import hyperadmin.auth as auth
        from hyperadmin.auth import (
            Group, GroupPermission, Permission, User, UserGroup, UserPermission, hash_password,
        )
        names = {"Group", "GroupPermission", "Permission", "User", "UserGroup",
                 "UserPermission", "hash_password", "metadata"}
        print(names <= set(auth.__all__), names <= set(dir(auth)), callable(hash_password))
        """
    )
    assert out == "True True True"


def test_unknown_attribute_raises_attribute_error() -> None:
    from hyperadmin import auth

    with pytest.raises(AttributeError, match="no_such_name"):
        auth.no_such_name  # noqa: B018 - attribute access is the behaviour under test


def test_metadata_returns_only_hyperadmin_tables() -> None:
    """Scenario: metadata() returns only hyperadmin tables."""
    out = _run(
        """
        from sqlmodel import Field, SQLModel

        class HostWidget(SQLModel, table=True):
            id: int | None = Field(default=None, primary_key=True)

        import hyperadmin.auth
        md = hyperadmin.auth.metadata()
        names = sorted(md.tables)
        print(all(n.startswith("hyperadmin_") for n in names), "hyperadmin_users" in names,
              "hostwidget" in names, md is not SQLModel.metadata)
        """
    )
    assert out == "True True False True"


def test_metadata_keeps_foreign_keys_between_auth_tables() -> None:
    out = _run(
        """
        import hyperadmin.auth
        md = hyperadmin.auth.metadata()
        fks = {fk.target_fullname for fk in md.tables["hyperadmin_user_groups"].foreign_keys}
        print(sorted(fks))
        """
    )
    assert out == "['hyperadmin_groups.id', 'hyperadmin_users.id']"


def test_metadata_warns_when_a_bridge_mode_admin_exists(monkeypatch, caplog) -> None:
    """SDD B.5: ``metadata()`` after a bridge-mode ``Admin`` logs a WARNING."""
    from hyperadmin import auth

    monkeypatch.setattr(auth, "_bridge_admin_constructed", False)
    auth._note_bridge_admin_constructed()

    with caplog.at_level("WARNING", logger="hyperadmin"):
        auth.metadata()

    assert any(r.levelname == "WARNING" and "bridge mode" in r.getMessage() for r in caplog.records)


def test_metadata_is_silent_without_a_bridge_mode_admin(monkeypatch, caplog) -> None:
    from hyperadmin import auth

    monkeypatch.setattr(auth, "_bridge_admin_constructed", False)
    with caplog.at_level("WARNING", logger="hyperadmin"):
        auth.metadata()

    assert not [r for r in caplog.records if r.levelname == "WARNING"]
