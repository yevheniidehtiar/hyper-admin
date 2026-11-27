"""Every ``HyperAdminSettings`` field has a row in a settings table of the docs.

v1.0 public API audit (st-v100-freeze-03), finding 10: the field names are public
(``docs/versioning.md``), but 23 of them appeared in no settings table.
"""

import re
from pathlib import Path

from hyperadmin.core.settings import HyperAdminSettings

DOCS = Path(__file__).resolve().parents[2] / "docs"
#: Developer-only folders; not published, so a row there documents nothing.
_UNPUBLISHED = ("specs", "design")
#: A table row naming a field: ``| `items_per_page` |`` or ``| `HYPERADMIN_ITEMS_PER_PAGE` |``.
_ROW = re.compile(r"^\|\s*`(?:HYPERADMIN_)?([A-Za-z0-9_]+)`", re.MULTILINE)
#: Read-only properties derived from the fields; not settings, no environment variable.
_DERIVED = ("database_engine_kwargs", "is_default_secret_key", "tzinfo")


def _documented_rows() -> set[str]:
    rows: set[str] = set()
    for page in DOCS.rglob("*.md"):
        if any(part in _UNPUBLISHED for part in page.relative_to(DOCS).parts):
            continue
        rows |= {name.lower() for name in _ROW.findall(page.read_text(encoding="utf-8"))}
    return rows


def test_every_setting_has_a_row_in_a_docs_settings_table() -> None:
    """
    Scenario: no setting is left undocumented
      Given every field of HyperAdminSettings
      When  the published docs pages are scanned for settings-table rows
      Then  each field has a row
    """
    missing = sorted(set(HyperAdminSettings.model_fields) - _documented_rows())

    assert missing == [], f"settings without a row in a docs settings table: {missing}"


def test_derived_properties_are_not_fields() -> None:
    """
    Scenario: derived properties are excluded from the settings table
      Given the read-only properties database_engine_kwargs, is_default_secret_key and tzinfo
      When  the settings fields are listed
      Then  none of them is a field (they have no environment variable)
      And   the application settings page says they are derived
    """
    assert not set(_DERIVED) & set(HyperAdminSettings.model_fields)
    application = (DOCS / "api" / "application.md").read_text(encoding="utf-8")
    assert all(f"`{name}`" in application for name in _DERIVED)
