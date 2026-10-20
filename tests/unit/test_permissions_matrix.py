"""Tests for the permission-matrix data layer (st-v057-pmx-01).

Covers ``load_grid``, ``compute_diff`` and ``save_diff`` from
``hyperadmin.permissions.matrix`` plus the ``Group.permissions_version``
column, following the scenarios in
``.meta/epics/epic-v057-permissions-matrix/stories/featpermissions-matrix-data-layer.md``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.models import Group, GroupPermission, Permission
from hyperadmin.auth.permissions import PermissionSyncService
from hyperadmin.permissions import (
    DEFAULT_ACTIONS,
    ConflictError,
    GroupNotFoundError,
    MatrixCell,
    MatrixChange,
    MatrixGrid,
    MatrixRow,
    PermissionMatrixService,
    UnknownPermissionError,
    compute_diff,
)

pytestmark = pytest.mark.anyio


class OrderAdmin:
    permissions: list[tuple[str, str]] = [("export_order", "Can export order")]


class InvoiceAdmin:
    permissions: list[tuple[str, str]] = []


REGISTERED = [("order", OrderAdmin), ("invoice", InvoiceAdmin)]


@pytest.fixture
async def engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'matrix.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def editors(engine) -> int:
    """The Editors group holding ``view_order``, ``change_order`` and ``view_invoice``."""
    await PermissionSyncService(engine=engine).sync_permissions(REGISTERED)
    async with AsyncSession(engine) as session:
        group = Group(name="Editors")
        session.add(group)
        await session.commit()
        await session.refresh(group)
        group_id = group.id
        assert group_id is not None
        perms = (await session.execute(select(Permission))).scalars().all()
        ids = {p.codename: p.id for p in perms}
        for codename in ("view_order", "change_order", "view_invoice"):
            session.add(GroupPermission(group_id=group_id, permission_id=ids[codename]))
        await session.commit()
        return group_id


@pytest.fixture
def service(engine) -> PermissionMatrixService:
    return PermissionMatrixService(engine=engine)


async def _granted(engine, group_id: int) -> set[str]:
    async with AsyncSession(engine) as session:
        stmt = (
            select(Permission.codename)
            .join(GroupPermission, GroupPermission.permission_id == Permission.id)
            .where(GroupPermission.group_id == group_id)
        )
        return set((await session.execute(stmt)).scalars().all())


async def _version(engine, group_id: int) -> int:
    async with AsyncSession(engine) as session:
        group = await session.get(Group, group_id)
        assert group is not None
        return group.permissions_version


async def _set_version(engine, group_id: int, version: int) -> None:
    async with AsyncSession(engine) as session:
        group = await session.get(Group, group_id)
        assert group is not None
        group.permissions_version = version
        session.add(group)
        await session.commit()


class TestGroupPermissionsVersion:
    def test_defaults_to_zero_with_server_default(self):
        """Scenario: Group.permissions_version added with default 0 (python and DDL)."""
        assert Group(name="Viewers").permissions_version == 0
        column = Group.__table__.c.permissions_version  # type: ignore[attr-defined]
        assert column.server_default is not None
        assert column.server_default.arg == "0"


class TestLoadGrid:
    async def test_one_cell_per_registered_model_and_action(self, service, editors):
        """Scenario: load_grid returns one entry per registered model x action."""
        grid = await service.load_grid(editors, REGISTERED)

        assert grid.group_id == editors
        assert grid.group_name == "Editors"
        assert grid.version == 0
        assert grid.actions == (*DEFAULT_ACTIONS, "export_order")
        assert [row.model for row in grid.rows] == ["order", "invoice"]
        order, invoice = grid.rows
        assert set(order.cells) == {"view", "add", "change", "delete", "export_order"}
        assert set(invoice.cells) == {"view", "add", "change", "delete"}
        assert order.cells["view"] == MatrixCell(codename="view_order", granted=True)
        assert order.cells["change"] == MatrixCell(codename="change_order", granted=True)
        assert order.cells["add"] == MatrixCell(codename="add_order", granted=False)
        assert order.cells["export_order"] == MatrixCell(codename="export_order", granted=False)
        assert invoice.cells["view"].granted is True
        assert invoice.cells["delete"].granted is False

    async def test_missing_group_raises(self, service, editors):
        """Scenario: load_grid for a deleted group raises GroupNotFoundError."""
        with pytest.raises(GroupNotFoundError) as excinfo:
            await service.load_grid(editors + 100, REGISTERED)
        assert excinfo.value.group_id == editors + 100

    async def test_defaults_to_the_admin_registry(self, service, editors, monkeypatch):
        """Scenario: load_grid(group_id) alone reads rows from the global admin registry."""
        from hyperadmin.core.registry import site

        class Invoice: ...

        monkeypatch.setattr(site, "_registry", {Invoice: InvoiceAdmin})

        grid = await service.load_grid(editors)

        assert [row.model for row in grid.rows] == ["invoice"]
        assert grid.rows[0].cells["view"].granted is True

    async def test_grid_helpers(self, service, editors):
        """Scenario: the grid answers cell / model / granted lookups for the view and audit."""
        grid = await service.load_grid(editors, REGISTERED)

        assert grid.cell("change_order") == MatrixCell(codename="change_order", granted=True)
        assert grid.cell("nope") is None
        assert grid.model_for("view_invoice") == "invoice"
        assert grid.model_for("nope") is None
        assert grid.granted_codenames() == {"view_order", "change_order", "view_invoice"}


def _grid(**granted: bool) -> MatrixGrid:
    rows = (
        MatrixRow(
            model="order",
            cells={
                "view": MatrixCell("view_order", granted.get("view_order", False)),
                "change": MatrixCell("change_order", granted.get("change_order", False)),
            },
        ),
        MatrixRow(
            model="invoice",
            cells={"view": MatrixCell("view_invoice", granted.get("view_invoice", False))},
        ),
    )
    return MatrixGrid(group_id=1, group_name="Editors", version=5, actions=("view",), rows=rows)


class TestComputeDiff:
    def test_returns_only_changed_cells_in_grid_order(self):
        """Scenario: compute_diff lists just the flipped cells, row by row."""
        grid = _grid(view_order=True, change_order=True)

        changes = compute_diff(
            grid, {"view_invoice": True, "change_order": False, "view_order": True}
        )

        assert changes == [
            MatrixChange(model="order", codename="change_order", granted=False),
            MatrixChange(model="invoice", codename="view_invoice", granted=True),
        ]

    def test_partial_submission_ignores_untouched_cells(self):
        """Scenario: a diff-only client sends a subset; unsent cells are not changes."""
        grid = _grid(view_order=True)

        assert compute_diff(grid, {"view_order": True}) == []
        assert compute_diff(grid, {}) == []

    def test_unknown_codename_raises(self):
        """Scenario: a tampered payload naming a codename outside the grid is rejected."""
        with pytest.raises(UnknownPermissionError) as excinfo:
            compute_diff(_grid(), {"delete_user": True, "view_order": True})
        assert excinfo.value.codenames == ("delete_user",)
        assert "delete_user" in str(excinfo.value)


class TestSaveDiff:
    async def test_matching_version_commits_and_bumps(self, service, engine, editors):
        """Scenario: save_diff with matching version commits and bumps."""
        await _set_version(engine, editors, 5)

        new_version = await service.save_diff(
            editors,
            5,
            [
                MatrixChange(model="order", codename="change_order", granted=False),
                MatrixChange(model="invoice", codename="add_invoice", granted=True),
            ],
        )

        assert new_version == 6
        assert await _version(engine, editors) == 6
        assert await _granted(engine, editors) == {"view_order", "view_invoice", "add_invoice"}

    async def test_is_idempotent_and_last_change_wins(self, service, engine, editors):
        """Scenario: re-granting a held cell or revoking an absent one writes nothing twice."""
        await service.save_diff(
            editors,
            0,
            [
                MatrixChange("order", "view_order", True),  # already held
                MatrixChange("order", "add_order", False),  # not held
                MatrixChange("order", "delete_order", False),
                MatrixChange("order", "delete_order", True),  # later change wins
            ],
        )

        assert await _granted(engine, editors) == {
            "view_order",
            "change_order",
            "view_invoice",
            "delete_order",
        }
        async with AsyncSession(engine) as session:
            rows = (await session.execute(select(GroupPermission))).scalars().all()
        assert len(rows) == 4

    async def test_stale_version_raises_conflict_and_mutates_nothing(
        self, service, engine, editors
    ):
        """Scenario: save_diff with stale version raises ConflictError."""
        await _set_version(engine, editors, 6)

        with pytest.raises(ConflictError) as excinfo:
            await service.save_diff(
                editors, 5, [MatrixChange("order", "change_order", granted=False)]
            )

        assert excinfo.value.group_id == editors
        assert excinfo.value.expected == 5
        assert excinfo.value.actual == 6
        assert "changed elsewhere" in str(excinfo.value)
        assert await _version(engine, editors) == 6
        assert await _granted(engine, editors) == {"view_order", "change_order", "view_invoice"}

    async def test_tampered_version_is_a_conflict(self, service, engine, editors):
        """Scenario: a browser sending version=-1 is treated as a version mismatch."""
        with pytest.raises(ConflictError):
            await service.save_diff(editors, -1, [MatrixChange("order", "add_order", True)])
        assert await _version(engine, editors) == 0
        assert "add_order" not in await _granted(engine, editors)

    async def test_deleted_group_raises_not_found(self, service, engine, editors):
        """Scenario: group deleted mid-edit → GroupNotFoundError, nothing written."""
        with pytest.raises(GroupNotFoundError):
            await service.save_diff(editors + 100, 0, [MatrixChange("order", "add_order", True)])
        with pytest.raises(GroupNotFoundError):
            await service.save_diff(editors + 100, 0, [])

    async def test_unknown_codename_rolls_back_the_version_bump(self, service, engine, editors):
        """Scenario: a codename without a Permission row aborts the save atomically."""
        with pytest.raises(UnknownPermissionError) as excinfo:
            await service.save_diff(
                editors,
                0,
                [
                    MatrixChange("order", "add_order", True),
                    MatrixChange("user", "delete_user", True),
                ],
            )

        assert excinfo.value.codenames == ("delete_user",)
        assert await _version(engine, editors) == 0
        assert "add_order" not in await _granted(engine, editors)

    async def test_empty_diff_validates_version_without_bumping(self, service, engine, editors):
        """Scenario: a no-op save still checks the version but leaves it unchanged."""
        assert await service.save_diff(editors, 0, []) == 0
        assert await _version(engine, editors) == 0

        with pytest.raises(ConflictError):
            await service.save_diff(editors, 3, [])

    async def test_works_with_a_host_session_factory(self, engine, editors):
        """Scenario: a host passes its own session maker instead of an engine."""
        service = PermissionMatrixService(session_factory=async_sessionmaker(engine))

        grid = await service.load_grid(editors, REGISTERED)
        new_version = await service.save_diff(
            editors, grid.version, compute_diff(grid, {"view_order": False})
        )

        assert new_version == 1
        assert "view_order" not in await _granted(engine, editors)

    def test_requires_engine_or_session_factory(self):
        """Scenario: constructing the service with neither source is a programming error."""
        with pytest.raises(ValueError, match="PermissionMatrixService"):
            PermissionMatrixService()
