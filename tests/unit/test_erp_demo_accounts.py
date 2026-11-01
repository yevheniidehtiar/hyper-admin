"""Unit tests for the ERP example's hosted-demo accounts and realtime settings (#785)."""

import importlib

import pytest
from examples.erp import seed
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select

from hyperadmin.auth.models import Permission, User, UserPermission


@pytest.fixture
async def demo_engine(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for content_type in ("invoice", "contact", "user", "group"):
            for action in ("view", "add", "change", "delete"):
                session.add(
                    Permission(
                        codename=f"{action}_{content_type}",
                        name=f"Can {action} {content_type}",
                        content_type=content_type,
                    )
                )
        await session.commit()
    monkeypatch.setattr(seed, "engine", engine)
    yield engine
    await engine.dispose()


async def _codenames(engine, username: str) -> set[str]:
    async with AsyncSession(engine) as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        rows = await session.execute(
            select(Permission.codename)
            .join(UserPermission, UserPermission.permission_id == Permission.id)  # type: ignore[arg-type]
            .where(UserPermission.user_id == user.id)
        )
        return set(rows.scalars().all())


async def test_seeding_creates_demo_demo2_and_demo_ro(demo_engine) -> None:
    """
    Scenario: seeding creates the three hosted-demo accounts
      Given a database with synced permissions
      When  seed_demo_user() runs
      Then  demo, demo2 and demo_ro exist
    """
    await seed.seed_demo_user()

    async with AsyncSession(demo_engine) as session:
        names = set((await session.execute(select(User.username))).scalars().all())
    assert names == {"demo", "demo2", "demo_ro"}


async def test_demo_and_demo2_share_permissions_without_auth_models(demo_engine) -> None:
    """
    Scenario: demo and demo2 hold the same non-auth permissions
      Given the three accounts are seeded
      Then  demo and demo2 hold every non-auth permission and no auth-model permission
    """
    await seed.seed_demo_user()

    demo = await _codenames(demo_engine, "demo")
    assert demo == await _codenames(demo_engine, "demo2")
    assert "change_invoice" in demo
    assert not {code for code in demo if code.endswith(("_user", "_group"))}


async def test_demo_ro_has_only_view_permissions_of_non_auth_models(demo_engine) -> None:
    """
    Scenario: demo_ro is read-only
      Given the three accounts are seeded
      Then  demo_ro holds only view_* permissions and none on auth models
    """
    await seed.seed_demo_user()

    assert await _codenames(demo_engine, "demo_ro") == {"view_invoice", "view_contact"}


async def test_seeding_is_idempotent(demo_engine) -> None:
    """
    Scenario: seeding twice changes nothing
      Given the accounts are already seeded
      When  seed_demo_user() runs again
      Then  no user or permission link is duplicated
    """
    await seed.seed_demo_user()
    await seed.seed_demo_user()

    async with AsyncSession(demo_engine) as session:
        users = (await session.execute(select(User))).scalars().all()
        links = (await session.execute(select(UserPermission))).scalars().all()
    assert len(users) == 3
    assert len(links) == len({(link.user_id, link.permission_id) for link in links})


@pytest.fixture
def erp_main(monkeypatch):
    monkeypatch.setenv("E2E_TESTING", "1")
    return importlib.import_module("examples.erp.main")


def test_realtime_settings_is_none_when_disabled(erp_main, monkeypatch) -> None:
    """
    Scenario: DEMO_REALTIME=0 turns realtime off
      Given DEMO_REALTIME is "0"
      When  _realtime_settings() is called
      Then  it returns None
    """
    monkeypatch.setenv("DEMO_REALTIME", "0")

    assert erp_main._realtime_settings() is None


def test_realtime_settings_uses_redis_when_configured(erp_main, monkeypatch) -> None:
    """
    Scenario: REDIS_URL puts pub/sub and presence on Redis
      Given REDIS_URL is set and DEMO_REALTIME is unset
      When  _realtime_settings() is called
      Then  both Redis URLs equal REDIS_URL and notifications are on
    """
    monkeypatch.delenv("DEMO_REALTIME", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    settings = erp_main._realtime_settings()

    assert settings is not None
    assert settings.pubsub_redis_url == "redis://redis:6379/0"
    assert settings.presence_redis_url == "redis://redis:6379/0"
    assert settings.notifications is True


def test_realtime_settings_defaults_to_in_memory(erp_main, monkeypatch) -> None:
    """
    Scenario: no REDIS_URL means in-memory backends
      Given neither DEMO_REALTIME nor REDIS_URL is set
      When  _realtime_settings() is called
      Then  settings are returned without Redis URLs
    """
    monkeypatch.delenv("DEMO_REALTIME", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    settings = erp_main._realtime_settings()

    assert settings is not None
    assert settings.pubsub_redis_url is None


def test_ledger_models_opt_out_of_notifications() -> None:
    """
    Scenario: ledger models are excluded
      Then JournalEntryAdmin and JournalLineAdmin set realtime_notifications=False
    """
    from examples.erp.accounting.admin import JournalEntryAdmin, JournalLineAdmin

    assert JournalEntryAdmin.options.realtime_notifications is False
    assert JournalLineAdmin.options.realtime_notifications is False
