"""``on_validation_error`` and ``on_auth_event`` fire from the views.

SDD ``docs/specs/plugin-registry.md``, hook table.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.dynamic import DynamicModelView
from hyperadmin.views.forms import PydanticForm
from tests.conftest import with_csrf

SECRET = "test-secret"


class HookProduct(SQLModel, table=True):
    __tablename__ = "test_hook_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float


class HookEvent(SQLModel, table=True):
    __tablename__ = "test_hook_event"
    id: int | None = Field(default=None, primary_key=True)
    starts: datetime


class _Recorder:
    name = "recorder"

    def __init__(self, fail_auth: bool = False) -> None:
        self.validation: list[dict[str, Any]] = []
        self.auth: list[dict[str, Any]] = []
        self.fail_auth = fail_auth

    def on_register(self, admin: Any) -> None:
        return None

    def on_validation_error(self, **kw: Any) -> None:
        self.validation.append(kw)

    def on_auth_event(self, **kw: Any) -> None:
        self.auth.append(kw)
        if self.fail_auth:
            raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


async def _build(tmp_path, recorder: _Recorder) -> tuple[FastAPI, Any]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'hooks.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        session.add_all(
            [
                User(
                    username="alice",
                    email="alice@example.com",
                    password_hash=hash_password("secret"),
                    is_superuser=True,
                ),
                User(
                    username="bob",
                    email="bob@example.com",
                    password_hash=hash_password("secret"),
                ),
            ]
        )
        await session.commit()
    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET),
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
    )
    assert admin.plugins.register(recorder, admin=admin)
    site.register(HookProduct, ModelAdmin)
    admin.mount("/admin")
    return app, engine


def _client(app: FastAPI) -> AsyncClient:
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return with_csrf(client, SECRET)


async def _login(client: AsyncClient, username: str, password: str = "secret"):  # noqa: S107
    return await client.post(
        "/admin/login", data={"username": username, "password": password}, follow_redirects=False
    )


@pytest.mark.anyio
async def test_failed_form_emits_validation_error_without_values(tmp_path) -> None:
    """
    Scenario: a failed form emits on_validation_error and never leaks input values
      Given a plugin records on_validation_error
      When  POST create with price="not-a-number"
      Then  the plugin received the model and the error type "float_parsing"
      And   the string "not-a-number" appears nowhere in field_errors
      And   the response is still the 422 form re-render
    """
    recorder = _Recorder()
    app, _ = await _build(tmp_path, recorder)
    async with _client(app) as client:
        await _login(client, "alice")
        response = await client.post(
            "/admin/hookproduct", data={"name": "n", "price": "not-a-number"}
        )
    assert response.status_code == 422
    assert len(recorder.validation) == 1
    event = recorder.validation[0]
    assert event["model"] is HookProduct
    assert event["admin"] is not None
    assert event["field_errors"] == {"price": ["float_parsing"]}
    assert "not-a-number" not in repr(event["field_errors"])


@pytest.mark.anyio
async def test_failed_update_form_emits_validation_error(tmp_path) -> None:
    """
    Scenario: a failed update form emits on_validation_error
      Given a plugin records on_validation_error and a product exists
      When  PUT the product with price="oops"
      Then  the plugin received field_errors for price
    """
    recorder = _Recorder()
    app, _ = await _build(tmp_path, recorder)
    async with _client(app) as client:
        await _login(client, "alice")
        created = await client.post(
            "/admin/hookproduct", data={"name": "n", "price": "1.5"}, follow_redirects=False
        )
        assert created.status_code == 303
        response = await client.put("/admin/hookproduct/1", data={"name": "n", "price": "oops"})
    assert response.status_code == 422
    assert recorder.validation[0]["field_errors"] == {"price": ["float_parsing"]}


@pytest.mark.anyio
async def test_unparsable_datetime_reports_datetime_parsing(tmp_path) -> None:
    """
    Scenario: a datetime the form cannot parse reports "datetime_parsing"
      Given a form with a datetime field
      When  it is validated with a garbage value
      Then  error_types maps the field to ["datetime_parsing"]
    """
    form = PydanticForm(HookEvent)
    instance, errs = form.validate({"starts": "not a date"})
    assert instance is None
    assert errs
    assert form.error_types == {"starts": ["datetime_parsing"]}


@pytest.mark.anyio
async def test_login_failure_and_success_and_logout_emit_events(tmp_path) -> None:
    """
    Scenario: login failure, login success and logout emit on_auth_event
      Given a plugin records on_auth_event
      When  alice fails to log in, logs in, then logs out
      Then  the events are login_failure (user None), login_success and logout
      And   the password is not among the arguments
    """
    recorder = _Recorder()
    app, _ = await _build(tmp_path, recorder)
    async with _client(app) as client:
        await _login(client, "alice", "wrong")
        await _login(client, "alice")
        await client.post("/admin/logout", follow_redirects=False)
    events = recorder.auth
    assert [e["event"] for e in events] == ["login_failure", "login_success", "logout"]
    assert events[0]["user"] is None
    assert events[0]["username"] == "alice"
    assert events[1]["user"].username == "alice"
    assert events[2]["username"] == "alice"
    for event in events:
        assert event["admin"] is not None
        assert event["request"] is not None
        assert "wrong" not in repr({k: v for k, v in event.items() if k != "request"})
        assert "password" not in event


@pytest.mark.anyio
async def test_denied_permission_emits_permission_denied(tmp_path) -> None:
    """
    Scenario: a denied permission emits permission_denied
      Given bob lacks every permission for HookProduct
      When  bob opens the product list
      Then  the response is 403
      And   the plugin received "permission_denied" for bob
    """
    recorder = _Recorder()
    app, _ = await _build(tmp_path, recorder)
    async with _client(app) as client:
        await _login(client, "bob")
        recorder.auth.clear()
        response = await client.get("/admin/hookproduct")
    assert response.status_code == 403
    assert [e["event"] for e in recorder.auth] == ["permission_denied"]
    assert recorder.auth[0]["username"] == "bob"
    assert recorder.auth[0]["user"].username == "bob"


@pytest.mark.anyio
async def test_any_permission_denial_emits_permission_denied() -> None:
    """
    Scenario: _check_any_permission denial emits permission_denied
      Given a user holding neither add nor change
      When  the either-permission check runs
      Then  403 is raised and permission_denied fired for the user
    """
    fired: list[tuple[str, dict[str, Any]]] = []

    class _Denier:
        async def has_permission(self, user: Any, codename: str) -> bool:
            return False

    view = object.__new__(DynamicModelView)
    view.permission_checker = _Denier()
    view._model_name_lower = "hookproduct"
    view.model = HookProduct
    view._hook_dispatcher = lambda hook, **kw: fired.append((hook, kw))
    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(username="bob")))
    with pytest.raises(HTTPException) as exc_info:
        await view._check_any_permission(request, ("add", "change"))  # type: ignore[arg-type]
    assert exc_info.value.status_code == 403
    assert fired[0][0] == "on_auth_event"
    assert fired[0][1]["event"] == "permission_denied"
    assert fired[0][1]["username"] == "bob"


@pytest.mark.anyio
async def test_failing_auth_handler_does_not_break_login(tmp_path) -> None:
    """
    Scenario: a failing handler does not break the request
      Given a plugin whose on_auth_event raises
      When  alice logs in with valid credentials
      Then  the login still succeeds with a redirect
    """
    recorder = _Recorder(fail_auth=True)
    app, _ = await _build(tmp_path, recorder)
    async with _client(app) as client:
        response = await _login(client, "alice")
    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin/")
    assert recorder.auth
