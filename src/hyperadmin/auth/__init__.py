"""Built-in authentication: models, password hashing and session auth.

Exports are resolved lazily (PEP 562). Importing ``hyperadmin.auth`` or one of
its submodules that does not need the ORM models (``middleware``, ``backend``,
``otp``) does **not** import ``hyperadmin.auth.models``, so the ``hyperadmin_*``
tables are only registered on ``SQLModel.metadata`` when a built-in model is
actually used. ``from hyperadmin.auth import User`` keeps working.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import MetaData
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from hyperadmin.auth.backend import hash_password
    from hyperadmin.auth.bridge import (
        BridgeDefaultPermissionChecker,
        CallablePermissionChecker,
        ExternalAuth,
        HostUserModelGuard,
        TokenCookie,
        build_admin_dependency,
        default_can_access,
        default_display_name,
        default_user_key,
    )
    from hyperadmin.auth.models import (
        Group,
        GroupPermission,
        Permission,
        User,
        UserGroup,
        UserPermission,
    )

_logger = logging.getLogger("hyperadmin")

_MODELS_MODULE = "hyperadmin.auth.models"
_BRIDGE_MODULE = "hyperadmin.auth.bridge"
_TABLE_PREFIX = "hyperadmin_"
_LAZY_EXPORTS: dict[str, str] = {
    "Group": _MODELS_MODULE,
    "GroupPermission": _MODELS_MODULE,
    "Permission": _MODELS_MODULE,
    "User": _MODELS_MODULE,
    "UserGroup": _MODELS_MODULE,
    "UserPermission": _MODELS_MODULE,
    "hash_password": "hyperadmin.auth.backend",
    "ExternalAuth": _BRIDGE_MODULE,
    "TokenCookie": _BRIDGE_MODULE,
    "CallablePermissionChecker": _BRIDGE_MODULE,
    "BridgeDefaultPermissionChecker": _BRIDGE_MODULE,
    "HostUserModelGuard": _BRIDGE_MODULE,
    "build_admin_dependency": _BRIDGE_MODULE,
    "default_can_access": _BRIDGE_MODULE,
    "default_display_name": _BRIDGE_MODULE,
    "default_user_key": _BRIDGE_MODULE,
}

__all__ = [
    "BridgeDefaultPermissionChecker",
    "CallablePermissionChecker",
    "ExternalAuth",
    "Group",
    "GroupPermission",
    "HostUserModelGuard",
    "Permission",
    "TokenCookie",
    "User",
    "UserGroup",
    "UserPermission",
    "build_admin_dependency",
    "default_can_access",
    "default_display_name",
    "default_user_key",
    "hash_password",
    "metadata",
]


# Set when an ``Admin`` in bridge mode (``auth=``) is built in this process.
_bridge_admin_constructed = False


def _note_bridge_admin_constructed() -> None:
    """Record that a bridge-mode ``Admin`` exists (called by the auth bridge)."""
    global _bridge_admin_constructed  # noqa: PLW0603 - process-wide flag by design
    _bridge_admin_constructed = True


def __getattr__(name: str) -> Any:
    """Resolve a legacy export on first access and cache it on the module."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})


def metadata() -> MetaData:
    """Return a new ``MetaData`` holding only the built-in ``hyperadmin_*`` tables.

    Intended as an Alembic ``target_metadata`` (or one of several) for hosts
    that use **built-in auth** (``Admin(auth_backend=...)``)::

        import hyperadmin.auth

        target_metadata = [Base.metadata, hyperadmin.auth.metadata()]

    The returned object is a copy: host tables are never included, and changing
    it does not affect ``SQLModel.metadata``.

    Note:
        Calling this imports ``hyperadmin.auth.models``. SQLModel table classes
        register on the global ``SQLModel.metadata`` when they are imported, so
        after this call the ``hyperadmin_*`` tables are also part of that
        process's ``SQLModel.metadata`` (and of any autogenerate target built
        from it). Hosts that bring their own auth should not call it; doing so
        after a bridge-mode ``Admin`` was built logs a WARNING.
    """
    if _bridge_admin_constructed:
        _logger.warning(
            "hyperadmin.auth.metadata() called while an Admin in bridge mode (auth=) "
            "exists: the built-in hyperadmin_* tables are now registered on "
            "SQLModel.metadata and will appear in Alembic autogenerate. Bridge-mode "
            "hosts do not need them."
        )
    importlib.import_module(_MODELS_MODULE)
    # The filter library's saved-views table (v0.5.6) is a hyperadmin_* table
    # every mounted admin uses, in both auth modes; register it here too so
    # init-db and Alembic hosts see it without having imported the views.
    importlib.import_module("hyperadmin.filters.saved_views")
    target = MetaData()
    for table in SQLModel.metadata.sorted_tables:
        if table.name.startswith(_TABLE_PREFIX):
            table.to_metadata(target)
    return target
