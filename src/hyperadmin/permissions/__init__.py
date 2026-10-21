"""Permission matrix: load, diff and save a group's model x action grid.

Opt-in like ``hyperadmin.auth``: importing this package imports the built-in
auth models, so only hosts using built-in auth should import it.
"""

from __future__ import annotations

from hyperadmin.permissions.audit import (
    OBJECT_RULE_ADDED,
    OBJECT_RULE_REMOVED,
    PERMISSION_CHANGE,
    PermissionAudit,
    audit_for_group,
    audit_rows,
    object_rule_row,
    write_audit,
)
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
from hyperadmin.permissions.object_rules import (
    GroupObjectPermission,
    ObjectRuleKey,
    ObjectRuleService,
)

__all__ = [
    "DEFAULT_ACTIONS",
    "OBJECT_RULE_ADDED",
    "OBJECT_RULE_REMOVED",
    "PERMISSION_CHANGE",
    "ConflictError",
    "GroupNotFoundError",
    "GroupObjectPermission",
    "MatrixCell",
    "MatrixChange",
    "MatrixGrid",
    "MatrixRow",
    "ObjectRuleKey",
    "ObjectRuleService",
    "PermissionAudit",
    "PermissionMatrixService",
    "UnknownPermissionError",
    "audit_for_group",
    "audit_rows",
    "compute_diff",
    "object_rule_row",
    "write_audit",
]
