"""Entry point the HyperAdmin plugin loader discovers (``hyperadmin.plugins`` group).

The plugin protocol is duck-typed: the core looks for a ``name`` and calls
``on_register(admin)`` once the admin is built. Registration contributes the
chart templates (``hyperadmin_reports/charts/...`` in the admin Jinja env) and
the chart CSS (served at ``{prefix}/static/plugins/reports/charts.css``). Report
routes arrive with the routes item.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

_PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = _PACKAGE_DIR / "templates"
STATIC_DIR = _PACKAGE_DIR / "static" / "hyperadmin_reports"


class ReportsPlugin:
    """The ``reports`` plugin: OLAP / pivot reports for HyperAdmin."""

    name: ClassVar[str] = "reports"

    def on_register(self, admin: Any) -> None:
        """Contribute the chart templates and static files to the admin."""
        admin.plugins.add_template_dir(self, TEMPLATES_DIR)
        admin.plugins.set_static_dir(self, STATIC_DIR)
