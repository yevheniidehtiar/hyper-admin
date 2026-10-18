"""The host application's own secrets (``examples/byoa``).

The host reads its session and JWT signing keys from the environment. So that
``uv run uvicorn examples.byoa.main:app`` works out of the box, a missing key
falls back to a fixed demo value and a warning is logged. A real app should
fail instead: read ``os.environ["..."]`` and let a missing key stop startup.

The admin's own key is not handled here: ``HyperAdminSettings()`` reads
``HYPERADMIN_SECRET_KEY`` and refuses the default key unless
``HYPERADMIN_DEBUG=true``.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def demo_secret(name: str, fallback: str) -> str:
    """Return the environment variable ``name``, or ``fallback`` with a warning.

    Demo-only fallback, never ship this.
    """
    value = os.environ.get(name)
    if value:
        return value
    logger.warning(
        "%s is not set: using a demo-only fallback secret. Never deploy this example as is.",
        name,
    )
    return fallback
