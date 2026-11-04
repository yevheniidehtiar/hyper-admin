"""Per-user sidebar state stored in the database: pinned pages (v0.5.9).

The nav tree itself is built in ``hyperadmin.core.navigation``; this package holds
what each user adds to it. See ``docs/specs/navigation-and-list-ux.md``.
"""

from hyperadmin.navigation.pins import DEFAULT_MAX_PINS, NavPin, NavPinService, PinLimitError

__all__ = ["DEFAULT_MAX_PINS", "NavPin", "NavPinService", "PinLimitError"]
