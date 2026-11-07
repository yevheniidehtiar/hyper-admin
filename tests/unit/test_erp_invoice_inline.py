"""The ERP showcase invoice form starts with a single empty item row (st-ux-erp-15)."""

from __future__ import annotations

import ast
from pathlib import Path

ADMIN = Path(__file__).resolve().parents[2] / "examples" / "erp" / "sales" / "admin.py"


def test_new_invoice_form_starts_with_one_empty_item_row() -> None:
    """
    Scenario: a new invoice form starts with one empty item row
      Given the ERP invoice admin declares an InvoiceItem inline
      Then  the inline asks for exactly one extra empty row
    """
    calls = [
        node
        for node in ast.walk(ast.parse(ADMIN.read_text()))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "InlineModelSpec"
    ]
    extras = [kw.value.value for call in calls for kw in call.keywords if kw.arg == "extra"]  # type: ignore[attr-defined]
    assert extras == [1]
