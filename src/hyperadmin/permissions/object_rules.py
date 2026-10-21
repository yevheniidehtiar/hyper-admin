"""Object rules: per-record permission entries of a group (the matrix's "Object" column).

An object rule says "group *g* may *codename* record *object_pk* of *model*".
They live in ``hyperadmin_group_object_permissions`` and are edited from the
matrix popover (``GET/POST {prefix}/permissions-matrix/object/{group}/{model}``,
``docs/specs/permission-matrix-ui.md``). Writes are idempotent and keyed on
``(group, model, codename, object_pk)``, so concurrent popover edits need no
version stamp. A host's :class:`~hyperadmin.core.auth.ObjectPermissionChecker`
reads them through :meth:`ObjectRuleService.rules_for`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, select

from hyperadmin.core.adapters import open_session, require_engine_or_session_factory

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from sqlalchemy.ext.asyncio import AsyncEngine

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory
    from hyperadmin.permissions.audit import PermissionAudit


class GroupObjectPermission(SQLModel, table=True):
    """One object rule of a group."""

    __tablename__ = "hyperadmin_group_object_permissions"  # type: ignore[reportIncompatibleVariableOverride]
    __table_args__ = (
        UniqueConstraint("group_id", "model", "codename", "object_pk", name="uq_group_object_rule"),
    )

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="hyperadmin_groups.id", index=True)
    #: Registered model slug (``model.__name__.lower()``), as the grid rows are keyed.
    model: str = Field(max_length=255)
    #: Action codename of the rule, e.g. ``change_order``.
    codename: str = Field(max_length=255)
    #: The record's primary key, as text.
    object_pk: str = Field(max_length=255)


@dataclass(frozen=True, slots=True)
class ObjectRuleKey:
    """What identifies one rule: the popover posts exactly these three values."""

    model: str
    codename: str
    object_pk: str


class ObjectRuleService:
    """Lists and edits object rules against the built-in auth tables."""

    def __init__(
        self, engine: AsyncEngine | None = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("ObjectRuleService", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        """Open a session from whichever of ``engine`` / ``session_factory`` was given."""
        return open_session(self.engine, self.session_factory)

    async def rules_for(self, group_id: int, model: str) -> list[GroupObjectPermission]:
        """The group's rules on ``model``, ordered by record then codename."""
        async with self._session() as session:
            return await self._rules(session, group_id, model)

    async def counts_for(self, group_id: int) -> dict[str, int]:
        """``model -> number of rules`` for the grid's "Object" column."""
        stmt = select(GroupObjectPermission.model).where(GroupObjectPermission.group_id == group_id)
        async with self._session() as session:
            models = (await session.execute(stmt)).scalars().all()
        return dict(Counter(models))

    async def add(
        self, group_id: int, key: ObjectRuleKey, *, audit: PermissionAudit | None = None
    ) -> bool:
        """Add the rule unless it exists; returns whether a row was written.

        ``audit`` is staged in the same transaction when a row is written.
        """
        async with self._session() as session:
            if await self._find(session, group_id, key) is not None:
                return False
            session.add(
                GroupObjectPermission(
                    group_id=group_id,
                    model=key.model,
                    codename=key.codename,
                    object_pk=key.object_pk,
                )
            )
            if audit is not None:
                session.add(audit)
            await session.commit()
            return True

    async def remove(
        self, group_id: int, key: ObjectRuleKey, *, audit: PermissionAudit | None = None
    ) -> bool:
        """Remove the rule if it exists; returns whether a row was deleted."""
        async with self._session() as session:
            existing = await self._find(session, group_id, key)
            if existing is None:
                return False
            await session.delete(existing)
            if audit is not None:
                session.add(audit)
            await session.commit()
            return True

    @staticmethod
    async def _rules(
        session: AsyncSessionLike, group_id: int, model: str
    ) -> list[GroupObjectPermission]:
        stmt = (
            select(GroupObjectPermission)
            .where(GroupObjectPermission.group_id == group_id, GroupObjectPermission.model == model)
            .order_by(GroupObjectPermission.object_pk, GroupObjectPermission.codename)  # type: ignore[arg-type]
        )
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def _find(
        session: AsyncSessionLike, group_id: int, key: ObjectRuleKey
    ) -> GroupObjectPermission | None:
        stmt = select(GroupObjectPermission).where(
            GroupObjectPermission.group_id == group_id,
            GroupObjectPermission.model == key.model,
            GroupObjectPermission.codename == key.codename,
            GroupObjectPermission.object_pk == key.object_pk,
        )
        return (await session.execute(stmt)).scalar_one_or_none()
