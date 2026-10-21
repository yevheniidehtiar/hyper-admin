"""Permission-matrix data layer: load a group's grid, diff it, save the diff.

The matrix is a **model x action** grid for one group (rows come from the
admin registry, columns from the default CRUD actions plus any custom
codenames a ``ModelAdmin`` declares in ``permissions``). Saves are
optimistic: every grid carries the group's ``permissions_version`` and
:meth:`PermissionMatrixService.save_diff` only commits when the version the
caller loaded is still current, bumping it atomically with the permission
rows. See ``docs/specs/permission-matrix-ui.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import update
from sqlmodel import select

from hyperadmin.auth.models import Group, GroupPermission, Permission
from hyperadmin.auth.permissions import generate_default_permissions
from hyperadmin.core.adapters import open_session, require_engine_or_session_factory

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Mapping
    from contextlib import AbstractAsyncContextManager

    from sqlalchemy.ext.asyncio import AsyncEngine

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory

#: Column order of the built-in CRUD actions; custom codenames follow them.
DEFAULT_ACTIONS: tuple[str, ...] = ("view", "add", "change", "delete")


class ConflictError(Exception):
    """The group's ``permissions_version`` moved since the grid was loaded.

    Nothing was written. The caller reloads the grid and retries with the new
    version (the view answers 409).
    """

    def __init__(self, group_id: int, *, expected: int, actual: int) -> None:
        super().__init__(
            f"permissions of group {group_id} changed elsewhere "
            f"(expected version {expected}, found {actual})"
        )
        self.group_id = group_id
        self.expected = expected
        self.actual = actual


class GroupNotFoundError(LookupError):
    """No group with the given id exists (deleted mid-edit; the view answers 404)."""

    def __init__(self, group_id: int) -> None:
        super().__init__(f"group {group_id} not found")
        self.group_id = group_id


class UnknownPermissionError(LookupError):
    """A codename is not in the grid or has no ``Permission`` row; nothing was written."""

    def __init__(self, codenames: Iterable[str]) -> None:
        self.codenames = tuple(sorted(codenames))
        super().__init__(f"unknown permission codenames: {', '.join(self.codenames)}")


@dataclass(frozen=True, slots=True)
class MatrixCell:
    """One checkbox of the grid: the codename it toggles and whether the group holds it."""

    codename: str
    granted: bool


@dataclass(frozen=True, slots=True)
class MatrixRow:
    """One registered model and its cells keyed by action (column) name.

    An action absent from ``cells`` does not apply to this model (the template
    renders a dash). Default actions are keyed ``view``/``add``/``change``/
    ``delete``; a custom codename is keyed by the codename itself.
    """

    model: str
    cells: Mapping[str, MatrixCell]


@dataclass(frozen=True, slots=True)
class MatrixGrid:
    """A group's full grid plus the version stamp a save must echo back."""

    group_id: int
    group_name: str
    version: int
    actions: tuple[str, ...]
    rows: tuple[MatrixRow, ...]

    def cell(self, codename: str) -> MatrixCell | None:
        """Return the cell for ``codename`` or ``None`` when the grid has no such cell."""
        return self._cells_by_codename().get(codename)

    def model_for(self, codename: str) -> str | None:
        """Return the row (model slug) that owns ``codename``, if any."""
        for row in self.rows:
            for cell in row.cells.values():
                if cell.codename == codename:
                    return row.model
        return None

    def granted_codenames(self) -> frozenset[str]:
        """Every codename the group currently holds in this grid."""
        return frozenset(
            cell.codename for row in self.rows for cell in row.cells.values() if cell.granted
        )

    def _cells_by_codename(self) -> dict[str, MatrixCell]:
        return {cell.codename: cell for row in self.rows for cell in row.cells.values()}


@dataclass(frozen=True, slots=True)
class MatrixChange:
    """One cell the operator flipped; the unit of the save payload and the audit log."""

    model: str
    codename: str
    granted: bool


def compute_diff(current: MatrixGrid, submitted: Mapping[str, bool]) -> list[MatrixChange]:
    """Return the cells whose submitted value differs from the loaded grid.

    Args:
        current: The grid the operator loaded.
        submitted: ``codename -> granted`` for the cells the client sends. A
            full-grid form post passes every codename; a diff-only client
            passes just the ones it touched. Order of the result follows the
            grid (row by row, column by column), so it is stable for the audit
            log regardless of client ordering.

    Raises:
        UnknownPermissionError: ``submitted`` names a codename the grid does
            not contain (a tampered or stale payload).
    """
    known = {cell.codename for row in current.rows for cell in row.cells.values()}
    unknown = set(submitted) - known
    if unknown:
        raise UnknownPermissionError(unknown)
    changes: list[MatrixChange] = []
    for row in current.rows:
        for cell in row.cells.values():
            if cell.codename not in submitted:
                continue
            wanted = bool(submitted[cell.codename])
            if wanted != cell.granted:
                changes.append(
                    MatrixChange(model=row.model, codename=cell.codename, granted=wanted)
                )
    return changes


class PermissionMatrixService:
    """Loads and saves the permission matrix against the built-in auth tables."""

    def __init__(
        self, engine: AsyncEngine | None = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("PermissionMatrixService", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        """Open a session from whichever of ``engine`` / ``session_factory`` was given."""
        return open_session(self.engine, self.session_factory)

    async def load_grid(
        self, group_id: int, registered_models: Iterable[tuple[str, Any]] | None = None
    ) -> MatrixGrid:
        """Build the grid for ``group_id``: one row per registered model, one cell per action.

        Args:
            group_id: Primary key of the group whose grid is edited.
            registered_models: ``(model_name, admin_class)`` tuples, the same
                shape ``PermissionSyncService.sync_permissions`` receives.
                Defaults to the global admin registry (``core.registry.site``).

        Raises:
            GroupNotFoundError: No group has that id.
        """
        if registered_models is None:
            registered_models = _site_registered_models()
        rows_spec = [
            (model_name, _row_codenames(model_name, admin_class))
            for model_name, admin_class in registered_models
        ]
        async with self._session() as session:
            group = await session.get(Group, group_id)
            if group is None:
                raise GroupNotFoundError(group_id)
            stmt = (
                select(Permission.codename)
                .join(
                    GroupPermission,
                    GroupPermission.permission_id == Permission.id,  # type: ignore[arg-type]
                )
                .where(GroupPermission.group_id == group_id)
            )
            granted = set((await session.execute(stmt)).scalars().all())
            group_name = group.name
            version = group.permissions_version

        actions: list[str] = list(DEFAULT_ACTIONS)
        rows: list[MatrixRow] = []
        for model_name, codenames in rows_spec:
            cells: dict[str, MatrixCell] = {}
            for action, codename in codenames.items():
                if action not in actions:
                    actions.append(action)
                cells[action] = MatrixCell(codename=codename, granted=codename in granted)
            rows.append(MatrixRow(model=model_name, cells=cells))
        return MatrixGrid(
            group_id=group_id,
            group_name=group_name,
            version=version,
            actions=tuple(actions),
            rows=tuple(rows),
        )

    async def save_diff(
        self,
        group_id: int,
        version: int,
        changes: Iterable[MatrixChange],
        *,
        before_commit: Callable[[AsyncSessionLike], Awaitable[None]] | None = None,
    ) -> int:
        """Apply ``changes`` to the group and bump its version, all in one transaction.

        The version check and the bump are a single conditional ``UPDATE``; when
        it matches no row the transaction is abandoned (the session is never
        committed), so a stale save, a deleted group or an unknown codename
        leaves every permission row untouched.

        Args:
            group_id: Primary key of the group being saved.
            version: The ``permissions_version`` the caller loaded with the grid.
            changes: Cells to flip; a later change for the same codename wins.
            before_commit: Awaited with the open session once the permission
                rows are staged and before the commit, so the caller can add
                rows that must land in the same transaction (the audit trail,
                ``permissions.audit``). Whatever it raises abandons the whole
                save. Not called for an empty ``changes``.

        Returns:
            The group's new ``permissions_version`` (unchanged when ``changes``
            is empty: a no-op save still validates the version but writes
            nothing).

        Raises:
            ConflictError: ``version`` is not the group's current version.
            GroupNotFoundError: No group has that id.
            UnknownPermissionError: A codename has no ``Permission`` row.
        """
        wanted: dict[str, bool] = {}
        for change in changes:
            wanted[change.codename] = change.granted
        async with self._session() as session:
            if not wanted:
                current = await self._current_version(session, group_id)
                if current != version:
                    raise ConflictError(group_id, expected=version, actual=current)
                return current

            bump = (
                update(Group)
                .where(Group.id == group_id, Group.permissions_version == version)  # type: ignore[arg-type]
                .values(permissions_version=version + 1)
            )
            if (await session.execute(bump)).rowcount != 1:
                current = await self._current_version(session, group_id)
                raise ConflictError(group_id, expected=version, actual=current)

            perms = (
                await session.execute(
                    select(Permission.id, Permission.codename).where(
                        Permission.codename.in_(wanted)  # type: ignore[attr-defined]
                    )
                )
            ).all()
            permission_ids = {codename: perm_id for perm_id, codename in perms}
            missing = set(wanted) - set(permission_ids)
            if missing:
                raise UnknownPermissionError(missing)

            held_stmt = select(GroupPermission).where(
                GroupPermission.group_id == group_id,
                GroupPermission.permission_id.in_(permission_ids.values()),  # type: ignore[attr-defined]
            )
            held = {
                row.permission_id: row for row in (await session.execute(held_stmt)).scalars().all()
            }
            for codename, granted in wanted.items():
                perm_id = permission_ids[codename]
                existing = held.get(perm_id)
                if granted and existing is None:
                    session.add(GroupPermission(group_id=group_id, permission_id=perm_id))
                elif not granted and existing is not None:
                    await session.delete(existing)
            if before_commit is not None:
                await before_commit(session)
            await session.commit()
        return version + 1

    @staticmethod
    async def _current_version(session: AsyncSessionLike, group_id: int) -> int:
        """Return the group's stored version, raising ``GroupNotFoundError`` when it is gone."""
        current = (
            await session.execute(select(Group.permissions_version).where(Group.id == group_id))
        ).scalar_one_or_none()
        if current is None:
            raise GroupNotFoundError(group_id)
        return int(current)


def _row_codenames(model_name: str, admin_class: Any) -> dict[str, str]:
    """``action -> codename`` for one model: the 4 defaults, then custom codenames."""
    codenames = {
        action: codename
        for action, (codename, _name) in zip(
            DEFAULT_ACTIONS, generate_default_permissions(model_name), strict=True
        )
    }
    for codename, _name in getattr(admin_class, "permissions", None) or []:
        codenames.setdefault(codename, codename)
    return codenames


def _site_registered_models() -> list[tuple[str, Any]]:
    """``(model_name, admin_class)`` tuples from the global registry (as ``Admin`` syncs them)."""
    from hyperadmin.core.registry import site  # noqa: PLC0415 - avoid importing at module load

    return [(model.__name__.lower(), admin_class) for model, admin_class in site._registry.items()]
