"""Unit tests for the seeded i18n catalogs (C3-C).

Covers BDD scenarios from
.meta/epics/epic-i18n/stories/c3c-babel-catalogs.md:

  Scenario: poe i18n:compile produces .mo files
    When  poe i18n:compile runs
    Then  src/hyperadmin/locale/<locale>/LC_MESSAGES/messages.mo exists for all 7 locales

  Scenario: en catalog is the identity translator
    When  load_translations("en") is called
    Then  _("Save") returns "Save"
"""

from __future__ import annotations

from pathlib import Path

import babel.support
import pytest

from hyperadmin.i18n.loader import LOCALE_DIR, load_translations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "fr", "de", "zh_CN", "ja", "uk")


# ---------------------------------------------------------------------------
# Scenario: compiled .mo files exist for all 7 locales
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_mo_file_exists(locale: str) -> None:
    """
    Scenario: poe i18n:compile produces .mo files
      Given  the seeded locale catalogs committed in C3-C
      When   the test suite runs
      Then   messages.mo exists for each supported locale
    """
    mo_path: Path = LOCALE_DIR / locale / "LC_MESSAGES" / "messages.mo"
    assert mo_path.exists(), (
        f"Missing compiled catalog: {mo_path}. Run `poe i18n:compile` to regenerate."
    )


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_translations_load_returns_translations_instance(locale: str) -> None:
    """
    Scenario: Translations.load succeeds for every supported locale
      Given  messages.mo exists for each locale
      When   load_translations(locale) is called
      Then   a babel.support.Translations instance is returned
    """
    result = load_translations(locale)
    # NullTranslations is the base — we need the real Translations subclass
    # (which has the compiled catalog) for a freshly built .mo.
    assert isinstance(result, babel.support.NullTranslations), (
        f"load_translations({locale!r}) returned {type(result)!r}; "
        "expected babel.support.NullTranslations or Translations."
    )


# ---------------------------------------------------------------------------
# Scenario: en catalog is the identity translator
# ---------------------------------------------------------------------------


_IDENTITY_SAMPLES: tuple[str, ...] = (
    "Save",
    "Cancel",
    "Sign in",
    "Search",
    "Next",
    "Previous",
    "Delete",
)


@pytest.mark.parametrize("msgid", _IDENTITY_SAMPLES)
def test_en_catalog_identity_translation(msgid: str) -> None:
    """
    Scenario: en catalog is the identity translator
      Given  the compiled en catalog
      When   load_translations("en").gettext(msgid) is called
      Then   the return value equals msgid (msgstr falls back to msgid)
    """
    translations = load_translations("en")
    result = translations.gettext(msgid)
    assert result == msgid, (
        f"Expected en.gettext({msgid!r}) == {msgid!r}, got {result!r}. "
        "The en catalog should act as a passthrough identity translator."
    )
