"""The ERP's own admin pages, contributed through the plugin API.

A host app does not need a packaged plugin to add a page to the sidebar: an object
with a ``name`` and ``on_register(admin)``, passed to ``admin.plugins.register()``
before ``admin.mount()``, gets its router mounted inside the admin (login, CSRF,
locale and error pages included) and its links placed in the sidebar group whose
label matches ``section``. Here the P&L report joins "Reports", next to the pages
of the ``hyperadmin-reports`` plugin when that is installed.
"""

from __future__ import annotations

from typing import Any, ClassVar

from examples.erp.reports.views import router

#: Admin-relative prefix of the ERP pages: the report is at ``/admin/erp/profit-loss``.
PAGE_PREFIX = "/erp"


class ErpPagesPlugin:
    """Mounts the Profit & Loss report and links it from the "Reports" sidebar group."""

    name: ClassVar[str] = "erp"

    def on_register(self, admin: Any) -> None:
        """Contribute the report page and its sidebar link."""
        admin.plugins.add_page(self, router, prefix=PAGE_PREFIX)
        admin.plugins.add_nav_entry(
            self,
            label="Profit & Loss",
            url_name="profit_loss_report",
            icon="bar-chart-3",
            section="Reports",
            order=-1,
            testid="nav-erp-profit-loss",
        )
