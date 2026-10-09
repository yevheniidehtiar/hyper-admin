"""Storage-root containment for file paths derived from database values.

A file column stores a name relative to the storage root. A value written into
the database by a user (or an attacker who can edit any text column) must never
let the admin read or delete a file outside that root, whether through an
absolute path, ``..`` segments or a symlink.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def storage_root(storage: Any) -> Path | None:
    """Return the resolved root directory of ``storage``, or ``None`` when unknown."""
    raw = getattr(storage, "_path", None) or getattr(storage, "path", None)
    if raw is None or callable(raw):
        return None
    try:
        return Path(raw).resolve()
    except (OSError, RuntimeError, TypeError):
        return None


def resolve_storage_path(storage: Any, name: str | None) -> Path | None:
    """Resolve ``name`` through ``storage`` and return it only if it stays inside the root.

    Args:
        storage: A ``FileSystemStorage`` (or compatible object exposing ``get_path``
            and a ``_path``/``path`` root).
        name: The stored file name, as held by the file column.

    Returns:
        The fully resolved path (symlinks followed) when it lies strictly inside
        the storage root, otherwise ``None``. Callers must treat ``None`` as
        "do not touch the filesystem".
    """
    if storage is None or not name:
        return None
    root = storage_root(storage)
    if root is None:
        return None
    try:
        candidate = Path(storage.get_path(str(name))).resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    if candidate == root or root not in candidate.parents:
        logger.warning("Refusing storage path outside the storage root: %r", name)
        return None
    return candidate
