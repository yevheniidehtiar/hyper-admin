"""Per-row outcome record for bulk-action execution.

See ``docs/specs/bulk-actions.md`` for the parent contract.
"""

from __future__ import annotations

from typing import Any, Literal, NamedTuple

BulkRowStatus = Literal["ok", "failed", "forbidden"]


class BulkRowResult(NamedTuple):
    """A single row's outcome from a bulk action run.

    Args:
        id: The primary key the bulk action targeted.
        status: ``"ok"`` (handler returned successfully),
            ``"failed"`` (handler raised a non-permission exception), or
            ``"forbidden"`` (object-level permission denied, or the handler
            raised ``HTTPException(403)``).
        detail: Optional human-readable detail (typically the exception's
            ``detail``/``str``). ``None`` for ``"ok"`` rows.
    """

    id: Any
    status: BulkRowStatus
    detail: str | None
