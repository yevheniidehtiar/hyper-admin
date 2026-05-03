"""Unit tests for translatable model verbose_name / verbose_name_plural.

Covers BDD scenarios from C2-E (v0.4.1 i18n epic):

  Scenario: verbose_name is a lazy string
    Given   class UserAdmin with verbose_name = gettext_lazy("User")
    When    the UserAdmin class is inspected
    Then    the attribute is a LazyProxy instance
    And     str(UserAdmin.verbose_name) == "User"

  Scenario: verbose_name renders translated in template context
    Given   .mo file mapping "User" -> "Usuario" for locale "es"
    And     the active translations catalog is set to "es"
    When    str(verbose_name) is evaluated
    Then    the output is "Usuario"

  Scenario: bare-string verbose_name still works (backward compat)
    Given   class ProductAdmin with verbose_name = "Product"
    When    the verbose_name attribute is inspected
    Then    str(verbose_name) == "Product"

  Scenario: gettext_lazy is importable from hyperadmin top-level
    Given   no prior import of hyperadmin.i18n
    When    `from hyperadmin import gettext_lazy` is executed
    Then    it returns a callable that produces LazyProxy objects
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import babel.support
import pytest

from hyperadmin.i18n import loader
from hyperadmin.i18n.loader import (
    _clear_caches,
    set_current_translations,
)

# ---------------------------------------------------------------------------
# Helpers shared with test_i18n_loader.py
# ---------------------------------------------------------------------------


def _write_mo(target: Path, locale: str, msgs: dict[str, str]) -> None:
    """Write a valid .mo binary for ``locale`` containing ``msgs``."""
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo

    catalog = Catalog(locale=locale, charset="utf-8")
    for msgid, msgstr in msgs.items():
        catalog.add(msgid, string=msgstr)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        write_mo(fh, catalog)


@pytest.fixture
def es_locale_dir(tmp_path: Path) -> Path:
    """Return a temp locale dir with Spanish translations for "User"."""
    _write_mo(
        tmp_path / "es" / "LC_MESSAGES" / "messages.mo",
        locale="es",
        msgs={"User": "Usuario"},
    )
    return tmp_path


@pytest.fixture(autouse=True)
def reset_i18n_state() -> Iterator[None]:
    """Reset LRU cache + contextvar between tests."""
    _clear_caches()
    token = set_current_translations(babel.support.NullTranslations())
    try:
        yield
    finally:
        loader.reset_current_translations(token)
        _clear_caches()


# ---------------------------------------------------------------------------
# Scenario: gettext_lazy re-exported from hyperadmin top-level
# ---------------------------------------------------------------------------


class TestGetTextLazyReExport:
    def test_importable_from_hyperadmin(self) -> None:
        """gettext_lazy is importable as `from hyperadmin import gettext_lazy`."""
        from hyperadmin import gettext_lazy

        proxy = gettext_lazy("Hello")
        assert isinstance(proxy, babel.support.LazyProxy)
        assert str(proxy) == "Hello"


# ---------------------------------------------------------------------------
# Scenario: verbose_name is a lazy string
# ---------------------------------------------------------------------------


class TestVerboseNameLazyProxy:
    def test_verbose_name_is_lazy_proxy(self) -> None:
        """A LazyProxy assigned as verbose_name remains a LazyProxy on the class."""
        from hyperadmin import gettext_lazy
        from hyperadmin.core.model import ModelAdmin

        class UserAdmin(ModelAdmin):
            verbose_name = gettext_lazy("User")

        assert isinstance(UserAdmin.verbose_name, babel.support.LazyProxy)

    def test_verbose_name_str_returns_msgid_without_catalog(self) -> None:
        """str(verbose_name) == "User" when no catalog is active."""
        from hyperadmin import gettext_lazy
        from hyperadmin.core.model import ModelAdmin

        class UserAdmin(ModelAdmin):
            verbose_name = gettext_lazy("User")

        assert str(UserAdmin.verbose_name) == "User"

    def test_get_verbose_name_returns_lazy_proxy(self) -> None:
        """get_verbose_name() returns the LazyProxy without pre-evaluating it."""
        from hyperadmin import gettext_lazy
        from hyperadmin.core.model import ModelAdmin

        class _FakeModel:
            __name__ = "FakeModel"

        class UserAdmin(ModelAdmin):
            verbose_name = gettext_lazy("User")

        result = UserAdmin.get_verbose_name(_FakeModel)
        assert isinstance(result, babel.support.LazyProxy)
        assert str(result) == "User"


# ---------------------------------------------------------------------------
# Scenario: verbose_name renders translated in template context
# ---------------------------------------------------------------------------


class TestVerboseNameTranslation:
    def test_verbose_name_renders_translated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        es_locale_dir: Path,
    ) -> None:
        """verbose_name renders "Usuario" when Spanish catalog is active."""
        from hyperadmin import gettext_lazy
        from hyperadmin.core.model import ModelAdmin
        from hyperadmin.i18n.loader import load_translations

        monkeypatch.setattr(loader, "LOCALE_DIR", es_locale_dir)
        _clear_caches()

        class UserAdmin(ModelAdmin):
            verbose_name = gettext_lazy("User")

        # Before installing the catalog, still shows msgid
        assert str(UserAdmin.verbose_name) == "User"

        translations = load_translations("es")
        token = set_current_translations(translations)
        try:
            assert str(UserAdmin.verbose_name) == "Usuario"
        finally:
            loader.reset_current_translations(token)

        # After resetting, back to msgid
        assert str(UserAdmin.verbose_name) == "User"

    def test_verbose_name_plural_rendered_translated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        es_locale_dir: Path,
    ) -> None:
        """verbose_name_plural renders correctly when catalog is active."""
        from hyperadmin import gettext_lazy
        from hyperadmin.core.model import ModelAdmin
        from hyperadmin.i18n.loader import load_translations

        # Add plural mapping
        _write_mo(
            es_locale_dir / "es" / "LC_MESSAGES" / "messages.mo",
            locale="es",
            msgs={"User": "Usuario", "Users": "Usuarios"},
        )
        monkeypatch.setattr(loader, "LOCALE_DIR", es_locale_dir)
        _clear_caches()

        class UserAdmin(ModelAdmin):
            verbose_name = gettext_lazy("User")
            verbose_name_plural = gettext_lazy("Users")

        translations = load_translations("es")
        token = set_current_translations(translations)
        try:
            assert str(UserAdmin.verbose_name_plural) == "Usuarios"
        finally:
            loader.reset_current_translations(token)


# ---------------------------------------------------------------------------
# Scenario: bare-string verbose_name still works (backward compat)
# ---------------------------------------------------------------------------


class TestVerboseNameBackwardCompat:
    def test_plain_string_verbose_name(self) -> None:
        """A plain string verbose_name is accepted and returned as-is."""
        from hyperadmin.core.model import ModelAdmin

        class ProductAdmin(ModelAdmin):
            verbose_name = "Product"

        assert ProductAdmin.verbose_name == "Product"
        assert str(ProductAdmin.verbose_name) == "Product"

    def test_plain_string_verbose_name_plural(self) -> None:
        """A plain string verbose_name_plural is accepted and returned as-is."""
        from hyperadmin.core.model import ModelAdmin

        class ProductAdmin(ModelAdmin):
            verbose_name = "Product"
            verbose_name_plural = "Products"

        assert str(ProductAdmin.verbose_name_plural) == "Products"

    def test_default_verbose_name_falls_back_to_model_name(self) -> None:
        """When verbose_name is None, get_verbose_name() returns model.__name__."""
        from hyperadmin.core.model import ModelAdmin

        class WidgetAdmin(ModelAdmin):
            pass  # no verbose_name set

        # model.__name__ is the class name as defined
        assert WidgetAdmin.get_verbose_name(WidgetAdmin) == "WidgetAdmin"

    def test_default_verbose_name_plural_appends_s(self) -> None:
        """When verbose_name_plural is None, get_verbose_name_plural() appends 's'."""
        from hyperadmin.core.model import ModelAdmin

        class _FakeModel:
            __name__ = "Widget"

        class WidgetAdmin(ModelAdmin):
            verbose_name = "Widget"

        result = WidgetAdmin.get_verbose_name_plural(_FakeModel)
        assert str(result) == "Widgets"

    def test_default_verbose_name_plural_lazy_plus_s(self) -> None:
        """Lazy verbose_name + 's' produces a string-like value == '<msgid>s'."""
        from hyperadmin import gettext_lazy
        from hyperadmin.core.model import ModelAdmin

        class _FakeModel:
            __name__ = "Widget"

        class WidgetAdmin(ModelAdmin):
            verbose_name = gettext_lazy("Widget")
            # verbose_name_plural intentionally omitted

        result = WidgetAdmin.get_verbose_name_plural(_FakeModel)
        # Should be "Widgets" (lazy + "s" evaluates to lazy proxy or plain string)
        assert str(result) == "Widgets"
