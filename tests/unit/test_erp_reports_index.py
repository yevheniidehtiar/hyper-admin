"""The ERP example's "All reports" page lists its reports.

The ``hyperadmin-reports`` plugin adds an "All reports" link to the sidebar's
Reports group whenever it is installed, and its index lists only registered
``ReportView`` classes. The ERP's Profit & Loss page and dashboard figures are
hand-built pages, so without its own reports the index read "No reports available".

Importing ``examples.erp`` registers the ERP models on the global ``SQLModel.metadata``
and ``site`` registry, so the check runs in a subprocess that prints a JSON result.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _run(body: str) -> Any:
    """Run ``body`` in a fresh interpreter and return the JSON it prints last."""
    env = {**os.environ, "E2E_TESTING": "1", "DEMO_REALTIME": "0"}
    env.pop("HYPERADMIN_DEMO", None)
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_all_reports_page_lists_the_erp_reports() -> None:
    """
    Scenario: the All reports page lists the ERP reports
      Given the ERP example with its seeded data
      When  the admin opens "All reports"
      Then  the page links to "Invoices by status" and "Bills by status"
      And   it no longer says "No reports available"
      And   each report page shows a grid of the seeded data, by status value ("Paid")
    """
    found = _run("""
        import json
        from fastapi.testclient import TestClient
        from examples.erp import main
        from tests.conftest import with_csrf

        with TestClient(main.app) as client:
            with_csrf(client, main.settings.secret_key)
            client.post("/admin/login", data={"username": "admin", "password": "admin"})
            index = client.get("/admin/reports/").text
            pages = {
                slug: client.get(f"/admin/reports/{slug}/")
                for slug in ("invoices-by-status", "bills-by-status")
            }
        print(json.dumps({
            "links": sorted(
                slug for slug in pages if f'data-testid="report-link-{slug}"' in index
            ),
            "empty": 'data-testid="report-index-empty"' in index,
            "status": {slug: page.status_code for slug, page in pages.items()},
            "paid": {slug: ">Paid<" in page.text for slug, page in pages.items()},
            "raw_enum": [slug for slug, page in pages.items() if "Status.PAID" in page.text],
        }))
    """)

    assert found["links"] == ["bills-by-status", "invoices-by-status"]
    assert found["empty"] is False
    assert found["status"] == {"invoices-by-status": 200, "bills-by-status": 200}
    assert found["paid"] == {"invoices-by-status": True, "bills-by-status": True}
    assert found["raw_enum"] == []
