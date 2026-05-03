"""Unit tests for C2-C: structured flash + translatable validation messages.

BDD scenarios from .meta/epics/epic-i18n/stories/c2c-translatable-validation.md:

Scenario: validation error message is a lazy string
  Given a form field with min_length=3
  When  views/forms.py constructs the error message
  Then  the message is wrapped in gettext_lazy (returns msgid before translation)
  And   str(msg) returns the English msgid

Scenario: flash message is a lazy string
  Given views/static.py emits a "Saved successfully" flash
  When  the flash is constructed
  Then  it is wrapped in gettext_lazy
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import babel.support
import pytest
from pydantic import BaseModel, Field

from hyperadmin.i18n import loader
from hyperadmin.i18n.loader import (
    _clear_caches,
    set_current_translations,
)
from hyperadmin.views.forms import PydanticForm

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_mo(target: Path, locale: str, msgs: dict[str, str]) -> None:
    """Write a real Babel .mo file at *target* containing *msgs*."""
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo

    catalog = Catalog(locale=locale, charset="utf-8")
    for msgid, msgstr in msgs.items():
        catalog.add(msgid, string=msgstr)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        write_mo(fh, catalog)


@pytest.fixture(autouse=True)
def reset_i18n_state() -> Iterator[None]:
    """Restore i18n context var and caches between tests."""
    _clear_caches()
    token = set_current_translations(babel.support.NullTranslations())
    try:
        yield
    finally:
        loader.reset_current_translations(token)
        _clear_caches()


# ---------------------------------------------------------------------------
# Scenario: flash message is a lazy string
# ---------------------------------------------------------------------------


class TestFlashMessagesAreLazy:
    def test_item_not_found_is_lazy_proxy(self) -> None:
        """
        Scenario: flash message is a lazy string
          Given views/static.py defines _MSG_ITEM_NOT_FOUND
          When  the module is imported
          Then  the message is a LazyProxy instance
        """
        # Given views/static.py emits a flash message
        import hyperadmin.views.static as static_mod

        # When the module constant is inspected
        msg = static_mod._MSG_ITEM_NOT_FOUND

        # Then it is a LazyProxy (gettext_lazy wraps it)
        assert isinstance(msg, babel.support.LazyProxy)

    def test_item_created_is_lazy_proxy(self) -> None:
        """
        Scenario: flash message is a lazy string
          Given views/static.py defines _MSG_ITEM_CREATED
          When  the module is imported
          Then  the message is a LazyProxy instance
        """
        import hyperadmin.views.static as static_mod

        msg = static_mod._MSG_ITEM_CREATED

        assert isinstance(msg, babel.support.LazyProxy)

    def test_item_updated_is_lazy_proxy(self) -> None:
        """
        Scenario: flash message is a lazy string
          Given views/static.py defines _MSG_ITEM_UPDATED
          When  the module is imported
          Then  the message is a LazyProxy instance
        """
        import hyperadmin.views.static as static_mod

        msg = static_mod._MSG_ITEM_UPDATED

        assert isinstance(msg, babel.support.LazyProxy)

    def test_flash_str_returns_english_msgid_without_catalog(self) -> None:
        """str(lazy_proxy) returns the msgid when no translation catalog is active."""
        import hyperadmin.views.static as static_mod

        # Given no catalog is installed (NullTranslations from fixture)
        # When str() is called on the lazy proxy
        result = str(static_mod._MSG_ITEM_NOT_FOUND)

        # Then it returns the English msgid
        assert result == "Item not found"

    def test_flash_translates_when_catalog_active(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """str(lazy_proxy) returns translated text when a catalog is active."""
        # Given a Spanish catalog that maps our msgids
        _write_mo(
            tmp_path / "es" / "LC_MESSAGES" / "messages.mo",
            locale="es",
            msgs={"Item not found": "Elemento no encontrado"},
        )
        monkeypatch.setattr(loader, "LOCALE_DIR", tmp_path)
        _clear_caches()
        translations = loader.load_translations("es")
        token = set_current_translations(translations)

        import hyperadmin.views.static as static_mod

        try:
            # When the locale is Spanish
            # Then str() returns the Spanish translation
            assert str(static_mod._MSG_ITEM_NOT_FOUND) == "Elemento no encontrado"
        finally:
            loader.reset_current_translations(token)


# ---------------------------------------------------------------------------
# Scenario: validation error message is a lazy string
# ---------------------------------------------------------------------------


class ShortNameModel(BaseModel):
    """Minimal model with a min_length constraint for testing."""

    name: str = Field(min_length=3)


class TestValidationErrorsAreLazy:
    def test_validation_error_is_lazy_proxy(self) -> None:
        """
        Scenario: validation error message is a lazy string
          Given a form field with min_length=3
          When  views/forms.py constructs the error message
          Then  the message is wrapped in gettext_lazy (a LazyProxy)
          And   str(msg) returns the English msgid
        """
        # Given a PydanticForm backed by ShortNameModel
        form = PydanticForm(ShortNameModel)

        # When validation fails (name too short)
        _instance, errs = form.validate({"name": "ab"})

        # Then errs["name"] contains a LazyProxy
        assert errs, "Expected validation errors but got none"
        name_errors = errs.get("name", [])
        assert name_errors, "Expected errors on 'name' field"
        first_error = name_errors[0]
        assert isinstance(first_error, babel.support.LazyProxy)

    def test_validation_error_str_returns_msgid(self) -> None:
        """str(proxy) returns the English msgid before any catalog is installed."""
        form = PydanticForm(ShortNameModel)
        _instance, errs = form.validate({"name": "ab"})

        name_errors = errs.get("name", [])
        assert name_errors

        # str() should return the English pydantic error message
        msg_str = str(name_errors[0])
        assert len(msg_str) > 0
        assert isinstance(msg_str, str)

    def test_field_errors_are_lazy_proxies(self) -> None:
        """FormField.errors are also LazyProxy after validate()."""
        form = PydanticForm(ShortNameModel)
        form.validate({"name": "x"})

        name_field = next((f for f in form.fields if f.name == "name"), None)
        assert name_field is not None
        assert name_field.errors is not None and len(name_field.errors) > 0
        assert isinstance(name_field.errors[0], babel.support.LazyProxy)

    def test_validation_error_translates_when_catalog_active(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """LazyProxy re-evaluates when locale changes, returning translated text."""
        # Build form and trigger validation error to capture the proxy
        form = PydanticForm(ShortNameModel)
        _instance, errs = form.validate({"name": "ab"})
        name_errors = errs.get("name", [])
        assert name_errors
        proxy = name_errors[0]
        msgid = str(proxy)  # English baseline

        # Given a catalog that translates the Pydantic error msgid
        translated = "El valor es demasiado corto"
        _write_mo(
            tmp_path / "es" / "LC_MESSAGES" / "messages.mo",
            locale="es",
            msgs={msgid: translated},
        )
        monkeypatch.setattr(loader, "LOCALE_DIR", tmp_path)
        _clear_caches()
        translations = loader.load_translations("es")
        token = set_current_translations(translations)

        try:
            # When the locale is Spanish, the proxy re-evaluates
            assert str(proxy) == translated
        finally:
            loader.reset_current_translations(token)
        # After locale reset, proxy returns the English msgid again
        assert str(proxy) == msgid

    def test_valid_form_has_empty_errors(self) -> None:
        """A passing validation produces no errors."""
        form = PydanticForm(ShortNameModel)
        instance, errs = form.validate({"name": "abc"})

        assert instance is not None
        assert errs == {}
