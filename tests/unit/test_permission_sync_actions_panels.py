"""``PermissionSyncService`` creates the action and detail-panel codenames the views check.

v1.0 public API audit (st-v100-freeze-03), finding 4: only the four CRUD codenames and
``ModelAdmin.permissions`` were synced, so with built-in auth only superusers could run a
custom action or open a detail panel.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import SQLModel, select
from starlette.responses import HTMLResponse

from hyperadmin.auth.models import Permission
from hyperadmin.auth.permissions import PermissionSyncService, generate_admin_permissions
from hyperadmin.core.actions import action, action_permission_codename
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.panels import PanelDef, panel


async def _render(request: Any, obj: Any) -> HTMLResponse:
    return HTMLResponse("panel")


class OrderAdmin(ModelAdmin):
    permissions = [("refund_order", "Can refund orders")]
    options = AdminOptions(
        panels=[
            PanelDef(slug="audit", label="Audit", handler=_render),
            PanelDef(slug="ledger", label="Ledger", handler=_render, permission="see_ledger"),
        ]
    )

    @action(label="Archive")
    async def archive(self, request: Any, item_id: Any) -> None:
        return None

    @action(label="Bulk archive", bulk=True)
    async def bulk_archive(self, request: Any, item_id: Any, *, params: Any = None) -> None:
        return None

    @panel("Invoice")
    async def invoice(self, request: Any, obj: Any) -> HTMLResponse:
        return HTMLResponse("invoice")


class InvoiceAdmin(ModelAdmin):
    @action(label="Archive")
    async def archive(self, request: Any, item_id: Any) -> None:
        return None


@pytest.fixture
async def engine(tmp_path: Any) -> AsyncEngine:
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'perms.db'}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


async def _codenames(engine: AsyncEngine) -> dict[str, tuple[str, str | None]]:
    async with AsyncSession(engine) as session:
        rows = (await session.execute(select(Permission))).scalars().all()
    return {row.codename: (row.name, row.content_type) for row in rows}


@pytest.mark.anyio
async def test_sync_creates_a_codename_per_custom_action(engine: AsyncEngine) -> None:
    """
    Scenario: every @action gets its action_<name>_<model> permission
      Given an OrderAdmin with the actions archive and bulk_archive
      When  PermissionSyncService syncs the registered models
      Then  action_archive_order and action_bulk_archive_order exist for "order"
    """
    await PermissionSyncService(engine).sync_permissions([("order", OrderAdmin)])

    stored = await _codenames(engine)
    assert stored["action_archive_order"] == ("Can run archive on order", "order")
    assert stored["action_bulk_archive_order"] == ("Can run bulk_archive on order", "order")


@pytest.mark.anyio
async def test_sync_creates_the_detail_panel_codenames(engine: AsyncEngine) -> None:
    """
    Scenario: every detail panel gets the codename it checks
      Given an OrderAdmin with an options-level panel, a panel with permission=, and a @panel
      When  PermissionSyncService syncs the registered models
      Then  view_order_panel_audit, see_ledger and view_order_panel_invoice exist
    """
    await PermissionSyncService(engine).sync_permissions([("order", OrderAdmin)])

    stored = await _codenames(engine)
    assert {"view_order_panel_audit", "see_ledger", "view_order_panel_invoice"} <= stored.keys()
    assert stored["view_order_panel_invoice"][1] == "order"


@pytest.mark.anyio
async def test_two_models_with_the_same_action_get_separate_permissions(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: an action name shared by two models is two permissions
      Given an OrderAdmin and an InvoiceAdmin that both declare archive
      When  PermissionSyncService syncs both models
      Then  action_archive_order and action_archive_invoice both exist
    """
    await PermissionSyncService(engine).sync_permissions(
        [("order", OrderAdmin), ("invoice", InvoiceAdmin)]
    )

    stored = await _codenames(engine)
    assert stored["action_archive_order"][1] == "order"
    assert stored["action_archive_invoice"][1] == "invoice"


@pytest.mark.anyio
async def test_sync_keeps_existing_rows_and_adds_no_duplicates(engine: AsyncEngine) -> None:
    """
    Scenario: syncing twice is idempotent
      Given the codenames of OrderAdmin were synced once
      When  PermissionSyncService syncs again
      Then  the permission table holds the same rows
    """
    service = PermissionSyncService(engine)
    await service.sync_permissions([("order", OrderAdmin)])
    first = await _codenames(engine)

    await service.sync_permissions([("order", OrderAdmin)])

    assert await _codenames(engine) == first


def test_generate_admin_permissions_lists_custom_then_actions_then_panels() -> None:
    """
    Scenario: the extra codenames come in a fixed order
      Given OrderAdmin with permissions, two actions and three panels
      When  generate_admin_permissions("order", OrderAdmin) runs
      Then  ModelAdmin.permissions come first, then the actions, then the panels
    """
    codenames = [codename for codename, _ in generate_admin_permissions("order", OrderAdmin)]

    assert codenames == [
        "refund_order",
        "action_archive_order",
        "action_bulk_archive_order",
        "view_order_panel_audit",
        "see_ledger",
        "view_order_panel_invoice",
    ]


def test_generate_admin_permissions_reads_only_permissions_from_a_non_class() -> None:
    """
    Scenario: an admin that is not a class contributes only its permissions list
      Given an object with a permissions attribute instead of a ModelAdmin class
      When  generate_admin_permissions runs on it
      Then  only those permissions are returned
    """

    class _Holder:
        permissions = [("export_order", "Can export orders")]

    assert generate_admin_permissions("order", _Holder()) == [("export_order", "Can export orders")]
    assert generate_admin_permissions("order", None) == []


def test_action_codename_matches_what_the_views_check() -> None:
    """
    Scenario: the synced action codename is the one the views ask for
      Given the archive action on the order model
      When  action_permission_codename("archive", "order") is built
      Then  it is "action_archive_order", the codename the action routes check
    """
    assert action_permission_codename("archive", "order") == "action_archive_order"
