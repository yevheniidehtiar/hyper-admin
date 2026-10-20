"""Permission matrix: load, diff and save a group's model x action grid.

Opt-in like ``hyperadmin.auth``: importing this package imports the built-in
auth models, so only hosts using built-in auth should import it.
"""

from __future__ import annotations

from hyperadmin.permissions.matrix import (
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

__all__ = [
    "DEFAULT_ACTIONS",
    "ConflictError",
    "GroupNotFoundError",
    "MatrixCell",
    "MatrixChange",
    "MatrixGrid",
    "MatrixRow",
    "PermissionMatrixService",
    "UnknownPermissionError",
    "compute_diff",
]
