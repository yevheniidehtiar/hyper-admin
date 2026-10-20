"""Entry point the HyperAdmin plugin loader discovers (``hyperadmin.plugins`` group).

The plugin protocol is duck-typed: the core looks for a ``name`` and calls
``on_register(admin)`` once the admin is built. Registration contributes the
chart templates (``hyperadmin_reports/charts/...``) and the report pages
(``reports/...``) to the admin Jinja env, the chart CSS (served at
``{prefix}/static/plugins/reports/charts.css``), the report pages under
``{prefix}/reports/`` with a "Reports" sidebar entry, and one permission
codename per report registered so far (``view_report_{slug}`` by default).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from hyperadmin_reports.routes import build_router
from hyperadmin_reports.view import registered_reports

_PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = _PACKAGE_DIR / "templates"
STATIC_DIR = _PACKAGE_DIR / "static" / "hyperadmin_reports"
#: Admin-relative prefix of the report pages.
PAGE_PREFIX = "/reports"


class ReportsPlugin:
    """The ``reports`` plugin: OLAP / pivot reports for HyperAdmin."""

    name: ClassVar[str] = "reports"

    def on_register(self, admin: Any) -> None:
        """Contribute templates, static files, the report pages, nav and permissions."""
        plugins = admin.plugins
        plugins.add_template_dir(self, TEMPLATES_DIR)
        plugins.set_static_dir(self, STATIC_DIR)
        plugins.add_page(self, build_router(admin), prefix=PAGE_PREFIX)
        plugins.add_nav_entry(self, label="Reports", url_name="reports-index", icon="file-text")
        declared: set[str] = set()
        for report in registered_reports():
            codename = report.get_permission()
            if codename in declared:  # several reports may share a custom codename
                continue
            declared.add(codename)
            plugins.add_permission(self, codename, name=f"Can view report {report.get_label()}")
