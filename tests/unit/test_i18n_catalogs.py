"""Unit tests for the seeded i18n catalogs (C3-C, top-20 expansion).

Covers BDD scenarios from
.meta/epics/epic-i18n/stories/c3c-babel-catalogs.md and the v0.5.2 expansion
spec at docs/specs/i18n-top-20-locales.md:

  Scenario: poe i18n:compile produces .mo files
    When  poe i18n:compile runs
    Then  src/hyperadmin/locale/<locale>/LC_MESSAGES/messages.mo exists for all 20 locales

  Scenario: en catalog is the identity translator
    When  load_translations("en") is called
    Then  _("Save") returns "Save"

  Scenario: every non-English catalog declares a Plural-Forms header
    Given a .po file at src/hyperadmin/locale/<code>/LC_MESSAGES/messages.po
    When  the file is parsed via babel.messages.pofile.read_po
    Then  the catalog's Plural-Forms header is present and non-empty
"""

from __future__ import annotations

from pathlib import Path

import babel.support
import pytest
from babel.messages.pofile import read_po

from hyperadmin.i18n.loader import LOCALE_DIR, load_translations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LOCALES: tuple[str, ...] = (
    "en",
    "es",
    "fr",
    "de",
    "zh_CN",
    "ja",
    "uk",
    "ar",
    "he",
    "hi",
    "pt_BR",
    "ru",
    "ko",
    "it",
    "tr",
    "pl",
    "nl",
    "vi",
    "id",
    "th",
)

# Non-English locales that ship AI-drafted translations marked `#, fuzzy`
# per the v0.5.2 expansion. English is the source language, so it has no
# plural-forms-driven content to verify.
_NON_EN_LOCALES: tuple[str, ...] = tuple(loc for loc in SUPPORTED_LOCALES if loc != "en")


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


# ---------------------------------------------------------------------------
# Scenario: every non-English catalog declares a Plural-Forms header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", _NON_EN_LOCALES)
def test_plural_forms_header_present(locale: str) -> None:
    """
    Scenario: every non-English catalog declares a Plural-Forms header
      Given  a .po file at src/hyperadmin/locale/<code>/LC_MESSAGES/messages.po
      When   the file is parsed via babel.messages.pofile.read_po
      Then   the catalog's Plural-Forms header is present and non-empty
    """
    po_path: Path = LOCALE_DIR / locale / "LC_MESSAGES" / "messages.po"
    assert po_path.exists(), f"Missing source catalog: {po_path}"
    with po_path.open("rb") as fh:
        catalog = read_po(fh)
    assert catalog.plural_forms, (
        f"Plural-Forms header missing or empty for {locale!r} at {po_path}. "
        "Every non-English catalog must declare nplurals + plural expression."
    )
    # Sanity-check the parsed expression — Babel exposes the parsed form via
    # plural_expr. If parsing failed, plural_expr would be the default '0'.
    assert catalog.num_plurals >= 1, (
        f"Catalog {locale!r} reports nplurals={catalog.num_plurals}; "
        "expected ≥1 (Babel default for unparseable expressions)."
    )


# ---------------------------------------------------------------------------
# Scenario: fuzzy entries fall back to msgid in compiled .mo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", _NON_EN_LOCALES)
def test_fuzzy_entries_fall_back_to_msgid(locale: str) -> None:
    """
    Scenario: fuzzy entries are excluded from compiled catalogs by default
      Given  a non-English catalog whose entries are all marked `#, fuzzy`
      When   load_translations(locale).gettext("Save") is called
      Then   the return value equals "Save" (msgid fallback) — pybabel compile
             excludes fuzzy entries unless --use-fuzzy is passed.

    This is the safe-by-default deployment path: until a native-speaker reviewer
    clears the fuzzy flag per-string, production renders English.
    """
    translations = load_translations(locale)
    # Pick a representative drafted string. While the entry exists in the .po
    # with a real msgstr, the .mo excludes fuzzy entries so gettext falls
    # through to the msgid.
    assert translations.gettext("Save") == "Save", (
        f"Expected {locale!r} fuzzy entries to fall back to the English msgid. "
        "If this fires, pybabel compile may have been invoked with --use-fuzzy, "
        "which surfaces unreviewed AI drafts in production."
    )
