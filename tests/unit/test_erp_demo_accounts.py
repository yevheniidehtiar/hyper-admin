"""Unit tests for the ERP example's hosted-demo accounts and realtime settings (#785).

Importing ``examples.erp`` registers the ERP models (including ``Account``) on the global
``SQLModel.metadata`` and ``site`` registry, which collides with other examples' models in
the same process. Every check therefore runs in a subprocess that prints a JSON result.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_SEED_PRELUDE = """
import asyncio, json
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from examples.erp import seed
from hyperadmin.auth.models import Permission, User, UserPermission

async def setup():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for ct in ("invoice", "contact", "user", "group"):
            for action in ("view", "add", "change", "delete"):
                session.add(Permission(codename=f"{action}_{ct}", name=action, content_type=ct))
        await session.commit()
    seed.engine = engine
    return engine

async def codenames(engine, username):
    async with AsyncSession(engine) as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        rows = await session.execute(
            select(Permission.codename)
            .join(UserPermission, UserPermission.permission_id == Permission.id)
            .where(UserPermission.user_id == user.id)
        )
        return sorted(rows.scalars().all())
"""


def _run(body: str, **env: str) -> Any:
    """Run ``body`` in a fresh interpreter and return the JSON it prints last."""
    script = _SEED_PRELUDE + textwrap.dedent(body)
    full_env = {**os.environ, "E2E_TESTING": "1", **env}
    for key in ("DEMO_REALTIME", "REDIS_URL"):
        if key not in env:
            full_env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_seeding_creates_demo_demo2_and_demo_ro() -> None:
    """
    Scenario: seeding creates the three hosted-demo accounts
      Given a database with synced permissions
      When  seed_demo_user() runs
      Then  demo, demo2 and demo_ro exist
    """
    names = _run("""
        async def main():
            engine = await setup()
            await seed.seed_demo_user()
            async with AsyncSession(engine) as session:
                print(json.dumps(sorted((await session.execute(select(User.username))).scalars().all())))
        asyncio.run(main())
    """)

    assert names == ["demo", "demo2", "demo_ro"]


def test_demo_and_demo2_share_permissions_without_auth_models() -> None:
    """
    Scenario: demo and demo2 hold the same non-auth permissions
      Given the three accounts are seeded
      Then  demo and demo2 hold every non-auth permission and no auth-model permission
    """
    demo, demo2 = _run("""
        async def main():
            engine = await setup()
            await seed.seed_demo_user()
            print(json.dumps([await codenames(engine, "demo"), await codenames(engine, "demo2")]))
        asyncio.run(main())
    """)

    assert demo == demo2
    assert "change_invoice" in demo
    assert not [code for code in demo if code.endswith(("_user", "_group"))]


def test_demo_ro_has_only_view_permissions_of_non_auth_models() -> None:
    """
    Scenario: demo_ro is read-only
      Given the three accounts are seeded
      Then  demo_ro holds only view_* permissions and none on auth models
    """
    codes = _run("""
        async def main():
            engine = await setup()
            await seed.seed_demo_user()
            print(json.dumps(await codenames(engine, "demo_ro")))
        asyncio.run(main())
    """)

    assert codes == ["view_contact", "view_invoice"]


def test_seeding_is_idempotent() -> None:
    """
    Scenario: seeding twice changes nothing
      Given the accounts are already seeded
      When  seed_demo_user() runs again
      Then  no user or permission link is duplicated
    """
    users, links, unique_links = _run("""
        async def main():
            engine = await setup()
            await seed.seed_demo_user()
            await seed.seed_demo_user()
            async with AsyncSession(engine) as session:
                users = (await session.execute(select(User))).scalars().all()
                links = (await session.execute(select(UserPermission))).scalars().all()
            pairs = {(link.user_id, link.permission_id) for link in links}
            print(json.dumps([len(users), len(links), len(pairs)]))
        asyncio.run(main())
    """)

    assert users == 3
    assert links == unique_links


def test_realtime_settings_is_none_when_disabled() -> None:
    """
    Scenario: DEMO_REALTIME=0 turns realtime off
      Given DEMO_REALTIME is "0"
      When  _realtime_settings() is called
      Then  it returns None
    """
    result = _run(
        """
        from examples.erp.main import _realtime_settings
        print(json.dumps(_realtime_settings() is None))
        """,
        DEMO_REALTIME="0",
    )

    assert result is True


def test_realtime_settings_uses_redis_when_configured() -> None:
    """
    Scenario: REDIS_URL puts pub/sub and presence on Redis
      Given REDIS_URL is set and DEMO_REALTIME is unset
      When  _realtime_settings() is called
      Then  both Redis URLs equal REDIS_URL and notifications are on
    """
    result = _run(
        """
        from examples.erp.main import _realtime_settings
        s = _realtime_settings()
        print(json.dumps([s.pubsub_redis_url, s.presence_redis_url, s.notifications]))
        """,
        REDIS_URL="redis://redis:6379/0",
    )

    assert result == ["redis://redis:6379/0", "redis://redis:6379/0", True]


def test_realtime_settings_defaults_to_in_memory() -> None:
    """
    Scenario: no REDIS_URL means in-memory backends
      Given neither DEMO_REALTIME nor REDIS_URL is set
      When  _realtime_settings() is called
      Then  settings are returned without Redis URLs
    """
    result = _run("""
        from examples.erp.main import _realtime_settings
        s = _realtime_settings()
        print(json.dumps([s is not None, s.pubsub_redis_url, s.presence_redis_url]))
    """)

    assert result == [True, None, None]


def test_ledger_models_opt_out_of_notifications() -> None:
    """
    Scenario: ledger models are excluded
      Then JournalEntryAdmin and JournalLineAdmin set realtime_notifications=False
    """
    result = _run("""
        from examples.erp.accounting.admin import JournalEntryAdmin, JournalLineAdmin
        print(json.dumps([
            JournalEntryAdmin.options.realtime_notifications,
            JournalLineAdmin.options.realtime_notifications,
        ]))
    """)

    assert result == [False, False]
