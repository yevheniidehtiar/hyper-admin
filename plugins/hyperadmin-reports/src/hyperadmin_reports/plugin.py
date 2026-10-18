"""Entry point the HyperAdmin plugin loader discovers (``hyperadmin.plugins`` group).

The plugin protocol is duck-typed: the core looks for a ``name`` and calls
``on_register(admin)`` once the admin is built. Report routes and registration
arrive with the routes item; until then registering the plugin is a no-op.
"""

from __future__ import annotations

from typing import Any, ClassVar


class ReportsPlugin:
    """The ``reports`` plugin: OLAP / pivot reports for HyperAdmin."""

    name: ClassVar[str] = "reports"

    def on_register(self, admin: Any) -> None:
        """Hook called by the core plugin loader; reports add no routes yet."""
