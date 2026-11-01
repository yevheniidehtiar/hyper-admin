"""Auth-enabled admin with the ``tasks`` plugin over a seeded in-memory backend, for the tasks E2E.

Started by the ``tasks_base_url`` fixture (``tests/e2e/plugins/conftest.py``) via uvicorn
subprocess. Users (password ``secret123``):

* ``alice`` - superuser, so she holds ``manage_tasks``.
* ``viewer`` - holds ``view_tasks`` only.

Seeded tasks: ``F1`` (failed, queue ``reports``, error ``boom``), ``P1`` (pending, ``reports``),
``R1`` (running, ``reports``) and ``E1`` (succeeded, ``emails``); schedules ``nightly`` (active)
and ``weekly`` (paused).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Permission, User, UserPermission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_tasks.backend import ScheduleRecord, TaskRecord, TaskState
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)

_NOW = datetime.now(UTC)


def _task(task_id: str, queue: str, state: TaskState, **fields: object) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        queue=queue,
        name="app.send_report",
        state=state,
        priority=0,
        attempt=1 if state is not TaskState.PENDING else 0,
        max_attempts=3,
        created_at=_NOW - timedelta(minutes=10),
        **fields,  # type: ignore[arg-type]
    )


def _schedule(schedule_id: str, cron: str, *, paused: bool) -> ScheduleRecord:
    return ScheduleRecord(
        id=schedule_id,
        task_name="app.send_report",
        queue="reports",
        cron=cron,
        misfire_policy="skip",
        paused=paused,
    )


backend = InMemoryTaskBackend()
backend.seed(
    [
        _task("F1", "reports", TaskState.FAILED, error="boom"),
        _task("P1", "reports", TaskState.PENDING),
        _task("R1", "reports", TaskState.RUNNING),
        _task("E1", "emails", TaskState.SUCCEEDED),
    ],
    schedules=[
        _schedule("nightly", "0 3 * * *", paused=False),
        _schedule("weekly", "0 4 * * 1", paused=True),
    ],
)


async def _seed_users() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password_hash=hash_password("secret123"),
                is_superuser=name == "alice",
            )
            for name in ("alice", "viewer")
        }
        session.add_all(users.values())
        await session.commit()
        view_tasks = (
            await session.execute(select(Permission).where(Permission.codename == "view_tasks"))
        ).scalar_one()
        session.add(UserPermission(user_id=users["viewer"].id, permission_id=view_tasks.id))
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await admin._sync_permissions()
    await _seed_users()
    yield


app = FastAPI(lifespan=lifespan)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, secret_key="e2e-tasks-secret"),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
admin.plugins["tasks"].lifecycle.backend = backend  # type: ignore[attr-defined]
