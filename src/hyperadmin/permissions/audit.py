"""Audit trail of permission changes: the ``hyperadmin_permission_audit`` table.

v0.5.1 deferred CRUD audit-log persistence to its own SDD, so there is no
shared writer yet; this module is the matrix's own trail and becomes an
adapter over the shared writer when one lands
(``docs/specs/permission-matrix-ui.md``, Goals). One row is written per
changed cell, in the same transaction as the permission rows: the matrix
view passes :func:`write_audit` as ``save_diff(before_commit=...)``, so a
failing audit write abandons the save and a committed save always has its
trail.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLModel resolves the column annotation at runtime
from typing import TYPE_CHECKING

from sqlmodel import Field, SQLModel, select

from hyperadmin.auth._types import UTCNaiveDateTime
from hyperadmin.core.timezones import utc_now

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hyperadmin.core.adapters import AsyncSessionLike
    from hyperadmin.permissions.matrix import MatrixChange

#: ``PermissionAudit.action`` of a matrix cell flip (group x model x codename).
PERMISSION_CHANGE = "permission_change"
#: ``PermissionAudit.action`` of an object rule added / removed in the popover.
OBJECT_RULE_ADDED = "object_rule_added"
OBJECT_RULE_REMOVED = "object_rule_removed"


class PermissionAudit(SQLModel, table=True):
    """One permission change: who flipped which cell of which group, from what to what.

    ``model``/``codename`` name the cell; for an object rule ``codename`` is the
    rule's action codename and ``object_pk`` the record it applies to.
    """

    __tablename__ = "hyperadmin_permission_audit"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    #: ``request.state.user_key`` of the operator (``str`` so host user ids fit).
    actor_key: str = Field(index=True, max_length=255)
    group_id: int = Field(index=True)
    action: str = Field(default=PERMISSION_CHANGE, max_length=64)
    model: str = Field(max_length=255)
    codename: str = Field(max_length=255)
    object_pk: str | None = Field(default=None, max_length=255)
    before: bool
    after: bool
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)


def audit_rows(
    actor_key: str, group_id: int, changes: Iterable[MatrixChange]
) -> list[PermissionAudit]:
    """Build the ``permission_change`` rows for a diff, in the diff's order.

    ``changes`` comes from :func:`~hyperadmin.permissions.matrix.compute_diff`,
    which only lists cells whose value flips, so ``before`` is the opposite of
    the submitted value.
    """
    return [
        PermissionAudit(
            actor_key=actor_key,
            group_id=group_id,
            action=PERMISSION_CHANGE,
            model=change.model,
            codename=change.codename,
            before=not change.granted,
            after=change.granted,
        )
        for change in changes
    ]


def object_rule_row(
    actor_key: str, group_id: int, *, model: str, codename: str, object_pk: str, added: bool
) -> PermissionAudit:
    """Build the audit row for an object rule that was added (or removed)."""
    return PermissionAudit(
        actor_key=actor_key,
        group_id=group_id,
        action=OBJECT_RULE_ADDED if added else OBJECT_RULE_REMOVED,
        model=model,
        codename=codename,
        object_pk=object_pk,
        before=not added,
        after=added,
    )


async def write_audit(session: AsyncSessionLike, rows: Iterable[PermissionAudit]) -> None:
    """Stage ``rows`` on ``session``; the caller's commit lands them with the save."""
    session.add_all(list(rows))


async def audit_for_group(session: AsyncSessionLike, group_id: int) -> list[PermissionAudit]:
    """Return the group's trail, oldest first."""
    stmt = (
        select(PermissionAudit)
        .where(PermissionAudit.group_id == group_id)
        .order_by(PermissionAudit.id)  # type: ignore[arg-type]
    )
    return list((await session.execute(stmt)).scalars().all())
