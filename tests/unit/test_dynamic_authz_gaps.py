"""Authorization and row-scoping gaps in ``DynamicModelView`` (st-v058-byoa-10).

Spec: ``docs/specs/bring-your-own-app.md`` sections B.6, A.3 and A.6.

Every test maps to a BDD scenario from the story. Each one exercises a live
security hole that existed before the fix:

- item handlers that skipped the model or object permission check;
- handlers that loaded rows outside the request-scoped queryset filter, so
  ``ModelAdmin.get_queryset`` (tenant / RLS scoping) was bypassed;
- ``delete_file_view`` deleting arbitrary server files through non-file columns
  or paths that resolve outside the storage root;
- inline formsets trusting a submitted child pk (IDOR and reparenting).
"""

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

import anyio
import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType
from sqlalchemy import Column, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.adapters import current_queryset_scope
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.core.storage_paths import resolve_storage_path
from hyperadmin.routing import HyperAdminRouter

_STORAGE_ROOT = tempfile.mkdtemp(prefix="hyperadmin-authz-")
_storage = FileSystemStorage(_STORAGE_ROOT)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AzCustomer(SQLModel, table=True):
    __tablename__ = "authz_customer"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    is_active: bool = True


class AzOrder(SQLModel, table=True):
    __tablename__ = "authz_order"

    id: int | None = Field(default=None, primary_key=True)
    status: str = "new"
    notes: str = ""
    tenant: str = "A"
    customer_id: int | None = Field(default=None, foreign_key="authz_customer.id")

    customer: Optional[AzCustomer] = Relationship()  # noqa: UP045
    lines: list["AzLine"] = Relationship(back_populates="order")


class AzLine(SQLModel, table=True):
    __tablename__ = "authz_line"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int | None = Field(default=None, foreign_key="authz_order.id")
    sku: str = ""
    qty: int = 1

    order: Optional[AzOrder] = Relationship(back_populates="lines")  # noqa: UP045


class AzInvoice(SQLModel, table=True):
    __tablename__ = "authz_invoice"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    pdf: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))


# ---------------------------------------------------------------------------
# Admins
# ---------------------------------------------------------------------------

ACTION_CALLS: list[Any] = []


class AzOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_editable = ["status"]

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        tenant = getattr(request.state, "tenant", None) if request is not None else None
        return {"tenant": tenant} if tenant else {}

    @action(label="Archive")
    async def archive(self, request: Request, item_id: Any) -> None:
        ACTION_CALLS.append(item_id)

    @action(label="Bulk archive", bulk=True)
    async def bulk_archive(self, request: Request, item_id: Any, *, params: Any = None) -> None:
        ACTION_CALLS.append(item_id)


class AzCustomerAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class AzInvoiceAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class AzLineAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


ALL_PERMS = frozenset(
    f"{verb}_{model}"
    for verb in ("view", "add", "change", "delete")
    for model in ("azorder", "azcustomer", "azline", "azinvoice")
) | {"action_archive_azorder", "action_bulk_archive_azorder"}


class _User:
    def __init__(self, perms: frozenset[str] | set[str] = ALL_PERMS) -> None:
        self.perms = frozenset(perms)
        self.is_superuser = False


class _PermChecker:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in user.perms


class _DenyObject:
    """Object permission checker that denies ``action`` on one order id."""

    def __init__(self, obj_id: int, action: str) -> None:
        self.obj_id = obj_id
        self.action = action

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return not (getattr(obj, "id", None) == self.obj_id and action == self.action)


class _PermAdmin(Admin):
    """``Admin`` that enforces ``permission_checker`` without a full auth backend."""

    def _register_views(self) -> None:
        router = HyperAdminRouter(
            engine=self.engine,
            templates=self.templates,
            permission_checker=self.permission_checker,
            storage=self.storage,
        )
        router.generate_routes()
        for r in router.get_routers():
            self.router.include_router(r)


@pytest.fixture(autouse=True)
def _clean() -> Any:
    site._registry = {}
    ACTION_CALLS.clear()
    yield
    site._registry = {}
    ACTION_CALLS.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed(engine: AsyncEngine, notes_for_5: str = "") -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    from sqlmodel.ext.asyncio.session import AsyncSession

    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(AzCustomer(id=1, name="alice", is_active=True))
        session.add(AzCustomer(id=2, name="bob", is_active=False))
        session.add(AzOrder(id=1, status="new", tenant="A"))
        session.add(AzOrder(id=2, status="new", tenant="A"))
        session.add(AzOrder(id=4, status="new", tenant="A"))
        session.add(AzOrder(id=5, status="new", tenant="B", notes=notes_for_5))
        session.add(AzLine(id=10, order_id=1, sku="line-10", qty=1))
        session.add(AzLine(id=20, order_id=2, sku="line-20", qty=2))
        session.add(AzInvoice(id=1, title="inv"))
        await session.commit()


def _build_app(
    engine: AsyncEngine,
    user: Any,
    *,
    tenant: str | None = None,
    object_checker: Any = None,
    order_admin: type[ModelAdmin] = AzOrderAdmin,
    adapter_class: type | None = None,
    register_line: bool = False,
) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def _attach(request: Request, call_next: Any) -> Any:
        request.state.user = user
        request.state.tenant = request.headers.get("x-tenant", tenant)
        return await call_next(request)

    admin = _PermAdmin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        permission_checker=_PermChecker(),
        storage=_storage,
    )
    site.register(AzCustomer, AzCustomerAdmin)
    site.register(
        AzOrder,
        order_admin,
        options=AdminOptions(
            list_editable=["status"],
            inlines=[InlineModelSpec(model=AzLine, fk_field="order_id", relationship_name="lines")],
            object_permission_checker=object_checker,
        ),
    )
    site.register(AzInvoice, AzInvoiceAdmin)
    if register_line:
        site.register(AzLine, AzLineAdmin)
    if adapter_class is not None:
        order_admin.adapter_class = adapter_class
    admin.mount(path="/admin")
    return app


def _client(
    user: Any = None,
    *,
    tenant: str | None = None,
    object_checker: Any = None,
    notes_for_5: str = "",
    register_line: bool = False,
) -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine, notes_for_5)
    app = _build_app(
        engine,
        user if user is not None else _User(),
        tenant=tenant,
        object_checker=object_checker,
        register_line=register_line,
    )
    return TestClient(app), engine


def _scalar(engine: AsyncEngine, sql: str) -> Any:
    async def _run() -> Any:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).first()

    return anyio.run(_run)


# ---------------------------------------------------------------------------
# Inline cell editing
# ---------------------------------------------------------------------------


def test_inline_cell_save_enforces_change_permission() -> None:
    """Scenario: inline cell save enforces change permission."""
    client, engine = _client(_User({"view_azorder"}))

    resp = client.post("/admin/azorder/1/inline/status", data={"status": "hacked"})

    assert resp.status_code == 403
    assert _scalar(engine, "SELECT status FROM authz_order WHERE id = 1")[0] == "new"


def test_inline_edit_form_enforces_object_permission() -> None:
    """Scenario: inline edit form enforces object permission."""
    client, _ = _client(object_checker=_DenyObject(1, "change"))

    resp = client.get("/admin/azorder/1/inline/status")

    assert resp.status_code == 403


def test_inline_edit_form_enforces_change_permission() -> None:
    client, _ = _client(_User({"view_azorder"}))

    assert client.get("/admin/azorder/1/inline/status").status_code == 403


def test_inline_save_respects_the_queryset_filter() -> None:
    """Scenario: inline save respects the queryset filter."""
    client, engine = _client(tenant="A")

    resp = client.post("/admin/azorder/5/inline/status", data={"status": "hacked"})

    assert resp.status_code == 404
    assert _scalar(engine, "SELECT status FROM authz_order WHERE id = 5")[0] == "new"


def test_inline_edit_form_respects_the_queryset_filter() -> None:
    client, _ = _client(tenant="A")

    assert client.get("/admin/azorder/5/inline/status").status_code == 404


# ---------------------------------------------------------------------------
# Inline add-row
# ---------------------------------------------------------------------------


def test_inline_add_row_requires_permission() -> None:
    """Scenario: inline add-row requires permission."""
    client, _ = _client(_User({"view_azorder"}))

    assert client.get("/admin/azorder/inline/azline/add-row").status_code == 403


def test_inline_add_row_allowed_with_change_permission() -> None:
    client, _ = _client(_User({"view_azorder", "change_azorder"}))

    assert client.get("/admin/azorder/inline/azline/add-row").status_code == 200


# ---------------------------------------------------------------------------
# Update form
# ---------------------------------------------------------------------------


def test_update_form_enforces_object_permission() -> None:
    client, _ = _client(object_checker=_DenyObject(1, "change"))

    assert client.get("/admin/azorder/1/edit").status_code == 403


# ---------------------------------------------------------------------------
# Single and bulk actions
# ---------------------------------------------------------------------------


def test_single_action_enforces_object_permission() -> None:
    """Scenario: single action enforces object permission."""
    client, _ = _client(object_checker=_DenyObject(1, "action_archive"))

    resp = client.post("/admin/azorder/1/action/archive", follow_redirects=False)

    assert resp.status_code == 403
    assert ACTION_CALLS == []


def test_single_action_respects_the_queryset_filter() -> None:
    """Scenario: single action respects the queryset filter."""
    client, _ = _client(tenant="A")

    resp = client.post("/admin/azorder/5/action/archive", follow_redirects=False)

    assert resp.status_code == 404
    assert ACTION_CALLS == []


def test_single_action_runs_for_visible_row() -> None:
    client, _ = _client(tenant="A")

    resp = client.post("/admin/azorder/1/action/archive", follow_redirects=False)

    assert resp.status_code == 303
    assert ACTION_CALLS == [1]


def test_bulk_action_respects_the_queryset_filter() -> None:
    """Scenario: bulk action respects the queryset filter."""
    client, _ = _client(tenant="A")

    resp = client.post("/admin/azorder/actions/bulk_archive/bulk", data={"ids": ["4", "5"]})

    assert resp.status_code == 200
    assert ACTION_CALLS == [4]
    assert "not found" in resp.text


# ---------------------------------------------------------------------------
# Request-scoped queryset filter
# ---------------------------------------------------------------------------


class _BarrierAdapter(SQLModelAdapter):
    """Adapter whose ``get`` waits until two requests are both inside it."""

    barrier: asyncio.Event | None = None
    waiting = 0

    async def get(self, pk: Any) -> Any:
        cls = type(self)
        cls.waiting += 1
        if cls.waiting >= 2 and cls.barrier is not None:
            cls.barrier.set()
        if cls.barrier is not None:
            await asyncio.wait_for(cls.barrier.wait(), timeout=5)
        return await super().get(pk)


@pytest.mark.anyio
async def test_a_queryset_filter_never_leaks_across_concurrent_requests() -> None:
    """Scenario: a queryset filter never leaks across concurrent requests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _seed(engine)
    order_admin = type("AzOrderBarrierAdmin", (AzOrderAdmin,), {})
    adapter_cls = type("BarrierAdapter", (_BarrierAdapter,), {"barrier": asyncio.Event()})
    app = _build_app(engine, _User(), order_admin=order_admin, adapter_class=adapter_cls)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp_a, resp_b = await asyncio.gather(
            client.get("/admin/azorder/1", headers={"x-tenant": "A"}),
            client.get("/admin/azorder/1", headers={"x-tenant": "B"}),
        )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 404


# ---------------------------------------------------------------------------
# File fields
# ---------------------------------------------------------------------------


def test_deleting_a_non_file_field_is_refused(tmp_path: Path) -> None:
    """Scenario: deleting a non-file field is refused."""
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    client, engine = _client(notes_for_5=str(victim))

    resp = client.delete("/admin/azorder/5/file/notes")

    assert resp.status_code == 404
    assert victim.exists()
    assert _scalar(engine, "SELECT notes FROM authz_order WHERE id = 5")[0] == str(victim)


def test_file_delete_never_leaves_the_storage_root(tmp_path: Path) -> None:
    """Scenario: file delete never leaves the storage root."""
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "victim.txt"
    victim.write_text("keep me")
    link = Path(_STORAGE_ROOT) / f"escape-{os.getpid()}-{tmp_path.name}"
    link.symlink_to(outside, target_is_directory=True)
    client, engine = _client()

    async def _point_at_victim() -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE authz_invoice SET pdf = :p WHERE id = 1"),
                {"p": f"{link.name}/victim.txt"},
            )

    anyio.run(_point_at_victim)
    try:
        client.delete("/admin/azinvoice/1/file/pdf")
    finally:
        link.unlink()

    assert victim.exists()


def test_resolve_storage_path_refuses_absolute_and_traversal_names() -> None:
    assert resolve_storage_path(_storage, "/etc/hosts") is None
    assert resolve_storage_path(_storage, "../../etc/hosts") is None
    assert resolve_storage_path(_storage, "") is None
    inside = resolve_storage_path(_storage, "docs/a.pdf")
    assert inside == Path(_STORAGE_ROOT).resolve() / "docs" / "a.pdf"


def test_upload_requires_a_file_field() -> None:
    client, _ = _client()

    resp = client.post(
        "/admin/azinvoice/upload/title", files={"file": ("a.txt", b"hello", "text/plain")}
    )

    assert resp.status_code == 404


def test_upload_to_a_file_field_succeeds() -> None:
    client, _ = _client()

    resp = client.post(
        "/admin/azinvoice/upload/pdf", files={"file": ("ok.txt", b"hello", "text/plain")}
    )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Inline formsets
# ---------------------------------------------------------------------------


def _order_form(**extra: str) -> dict[str, str]:
    return {"status": "edited", "notes": "", "tenant": "A", **extra}


def test_inline_formset_rejects_another_parents_child_row() -> None:
    """Scenario: inline formset rejects another parent's child row."""
    client, engine = _client()

    resp = client.put(
        "/admin/azorder/1",
        data=_order_form(**{"azline-0-pk": "20", "azline-0-sku": "stolen", "azline-0-qty": "9"}),
        follow_redirects=False,
    )

    assert resp.status_code == 404
    assert tuple(_scalar(engine, "SELECT order_id, sku, qty FROM authz_line WHERE id = 20")) == (
        2,
        "line-20",
        2,
    )
    assert _scalar(engine, "SELECT status FROM authz_order WHERE id = 1")[0] == "new"


def test_inline_formset_cannot_delete_another_parents_child_row() -> None:
    """Scenario: inline formset cannot delete another parent's child row."""
    client, engine = _client()

    resp = client.put(
        "/admin/azorder/1",
        data=_order_form(**{"azline-0-pk": "20", "azline-0-DELETE": "on"}),
        follow_redirects=False,
    )

    assert resp.status_code == 404
    assert _scalar(engine, "SELECT id FROM authz_line WHERE id = 20") is not None


def test_inline_formset_still_updates_own_child_row() -> None:
    client, engine = _client()

    resp = client.put(
        "/admin/azorder/1",
        data=_order_form(**{"azline-0-pk": "10", "azline-0-sku": "renamed", "azline-0-qty": "3"}),
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert tuple(_scalar(engine, "SELECT order_id, sku FROM authz_line WHERE id = 10")) == (
        1,
        "renamed",
    )


def test_inline_create_cannot_claim_an_existing_child_row() -> None:
    client, engine = _client()

    resp = client.post(
        "/admin/azorder",
        data=_order_form(**{"azline-0-pk": "20", "azline-0-sku": "stolen", "azline-0-qty": "9"}),
        follow_redirects=False,
    )

    assert resp.status_code == 404
    assert tuple(_scalar(engine, "SELECT order_id, sku FROM authz_line WHERE id = 20")) == (
        2,
        "line-20",
    )
    assert _scalar(engine, "SELECT count(*) FROM authz_order")[0] == 4


def test_inline_formset_enforces_inline_model_add_permission() -> None:
    perms = ALL_PERMS - {"add_azline"}
    client, engine = _client(_User(perms), register_line=True)

    resp = client.put(
        "/admin/azorder/1",
        data=_order_form(**{"azline-0-sku": "new-line", "azline-0-qty": "1"}),
        follow_redirects=False,
    )

    assert resp.status_code == 403
    assert _scalar(engine, "SELECT id FROM authz_line WHERE sku = 'new-line'") is None


def test_inline_formset_enforces_inline_model_delete_permission() -> None:
    perms = ALL_PERMS - {"delete_azline"}
    client, engine = _client(_User(perms), register_line=True)

    resp = client.put(
        "/admin/azorder/1",
        data=_order_form(**{"azline-0-pk": "10", "azline-0-DELETE": "on"}),
        follow_redirects=False,
    )

    assert resp.status_code == 403
    assert _scalar(engine, "SELECT id FROM authz_line WHERE id = 10") is not None


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------


def test_choices_require_view_permission_on_the_target_model() -> None:
    """Scenario: choices require view permission on the target model."""
    client, _ = _client(_User({"view_azorder"}))

    assert client.get("/admin/azorder/choices/customer").status_code == 403


def test_choices_allowed_with_view_on_source_and_target() -> None:
    client, _ = _client(_User({"view_azorder", "view_azcustomer"}))

    assert client.get("/admin/azorder/choices/customer").status_code == 200


# ---------------------------------------------------------------------------
# Every adapter call runs inside the request scope
# ---------------------------------------------------------------------------

_SCOPED_METHODS = (
    "get",
    "list",
    "create",
    "update",
    "delete",
    "get_related",
    "get_choices",
    "save_inline_rows",
)


class _RecordingAdapter(SQLModelAdapter):
    calls: list[tuple[str, bool]] = []


def _make_recorder(name: str) -> Any:
    async def _wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        type(self).calls.append((name, current_queryset_scope() is not None))
        return await getattr(SQLModelAdapter, name)(self, *args, **kwargs)

    return _wrapper


for _name in _SCOPED_METHODS:
    setattr(_RecordingAdapter, _name, _make_recorder(_name))


def test_every_handler_calls_the_adapter_inside_the_request_scope() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine)
    order_admin = type("AzOrderRecordingAdmin", (AzOrderAdmin,), {})
    adapter_cls = type("RecordingAdapter", (_RecordingAdapter,), {"calls": []})
    client = TestClient(
        _build_app(engine, _User(), order_admin=order_admin, adapter_class=adapter_cls)
    )

    responses = [
        client.get("/admin/azorder"),
        client.get("/admin/azorder/1"),
        client.get("/admin/azorder/create"),
        client.post("/admin/azorder", data=_order_form(), follow_redirects=False),
        client.get("/admin/azorder/1/edit"),
        client.put(
            "/admin/azorder/1",
            data=_order_form(**{"azline-0-pk": "10", "azline-0-sku": "x", "azline-0-qty": "1"}),
            follow_redirects=False,
        ),
        client.get("/admin/azorder/1/inline/status"),
        client.post("/admin/azorder/1/inline/status", data={"status": "s"}),
        client.get("/admin/azorder/choices/customer"),
        client.get("/admin/azorder/create-popup?target=order"),
        client.post("/admin/azorder/1/action/archive", follow_redirects=False),
        client.post("/admin/azorder/actions/bulk_archive/bulk", data={"ids": ["1"]}),
        client.delete("/admin/azorder/4", follow_redirects=False),
    ]

    assert all(r.status_code < 400 for r in responses), [r.status_code for r in responses]
    called = {name for name, _ in adapter_cls.calls}
    assert called >= set(_SCOPED_METHODS), set(_SCOPED_METHODS) - called
    outside = [name for name, in_scope in adapter_cls.calls if not in_scope]
    assert outside == []


# ---------------------------------------------------------------------------
# Review follow-ups: related rows embedded in pages, uploads, unregistered models
# ---------------------------------------------------------------------------

_NO_CUSTOMER_VIEW = {"view_azorder", "add_azorder", "change_azorder"}


def _link_order_to_customer(engine: AsyncEngine, order_id: int, customer_id: int) -> None:
    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE authz_order SET customer_id = :c WHERE id = :o"),
                {"c": customer_id, "o": order_id},
            )

    anyio.run(_run)


@pytest.mark.parametrize(
    "path", ["/admin/azorder", "/admin/azorder/create", "/admin/azorder/1/edit"]
)
def test_pages_do_not_embed_target_rows_without_view_on_the_target(path: str) -> None:
    """Scenario: pages never embed related rows the user may not view."""
    client, _ = _client(_User(_NO_CUSTOMER_VIEW))

    resp = client.get(path)

    assert resp.status_code == 200
    assert "alice" not in resp.text
    assert "bob" not in resp.text


def test_pages_embed_target_rows_with_view_on_the_target() -> None:
    client, _ = _client(_User(_NO_CUSTOMER_VIEW | {"view_azcustomer"}))

    resp = client.get("/admin/azorder/create")

    assert resp.status_code == 200
    assert "alice" in resp.text


def test_edit_form_keeps_the_selected_target_without_view_on_the_target() -> None:
    """The current FK value survives a save even when the target labels are hidden."""
    client, engine = _client(_User(_NO_CUSTOMER_VIEW))
    _link_order_to_customer(engine, 1, 2)

    resp = client.get("/admin/azorder/1/edit")

    assert resp.status_code == 200
    assert "bob" not in resp.text
    assert re.search(r'<option[^>]*value="2"[^>]*selected', resp.text)


def test_upload_never_overwrites_an_existing_file() -> None:
    """Scenario: an upload cannot overwrite another record's file."""
    existing = Path(_STORAGE_ROOT) / f"tenantB-{os.getpid()}" / "contract.pdf"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"ORIGINAL")
    client, _ = _client(_User({"add_azinvoice"}))

    resp = client.post(
        "/admin/azinvoice/upload/pdf",
        files={"file": (f"{existing.parent.name}/contract.pdf", b"PWNED", "application/pdf")},
    )

    assert resp.status_code == 200
    assert existing.read_bytes() == b"ORIGINAL"
    stored = resp.json()["filename"]
    assert not os.path.isabs(stored)
    assert "/" not in stored
    assert (Path(_STORAGE_ROOT) / stored).read_bytes() == b"PWNED"


def test_upload_with_the_same_name_twice_keeps_both_files() -> None:
    client, _ = _client()

    first = client.post("/admin/azinvoice/upload/pdf", files={"file": ("dup.txt", b"one")})
    second = client.post("/admin/azinvoice/upload/pdf", files={"file": ("dup.txt", b"two")})

    assert first.json()["filename"] != second.json()["filename"]
    assert (Path(_STORAGE_ROOT) / first.json()["filename"]).read_bytes() == b"one"
    assert (Path(_STORAGE_ROOT) / second.json()["filename"]).read_bytes() == b"two"


_NO_LINE_PERMS = frozenset(p for p in ALL_PERMS if not p.endswith("_azline"))


def test_unregistered_inline_model_falls_back_to_parent_permission_on_create() -> None:
    """Scenario: staff with rights on the parent can add rows of an unregistered inline."""
    client, engine = _client(_User(_NO_LINE_PERMS))

    resp = client.post(
        "/admin/azorder",
        data=_order_form(**{"azline-0-sku": "new", "azline-0-qty": "1"}),
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert _scalar(engine, "SELECT id FROM authz_line WHERE sku = 'new'") is not None


def test_unregistered_inline_model_falls_back_to_parent_permission_on_update() -> None:
    client, _ = _client(_User(_NO_LINE_PERMS))

    resp = client.put(
        "/admin/azorder/1",
        data=_order_form(**{"azline-0-pk": "10", "azline-0-sku": "line-10", "azline-0-qty": "1"}),
        follow_redirects=False,
    )

    assert resp.status_code == 303


def test_choices_on_an_unregistered_target_fall_back_to_the_source_permission() -> None:
    client, _ = _client(_User({"view_azorder"}))

    assert client.get("/admin/azorder/choices/lines").status_code == 200


def test_choices_on_a_registered_inline_target_still_require_its_view_permission() -> None:
    client, _ = _client(_User({"view_azorder"}), register_line=True)

    assert client.get("/admin/azorder/choices/lines").status_code == 403
