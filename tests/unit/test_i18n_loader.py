"""Unit tests for hyperadmin.i18n.loader.

Covers BDD scenarios from
.meta/epics/epic-i18n/stories/c1c-jinja-i18n-loader.md.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import babel.support
import pytest
from jinja2 import Environment

from hyperadmin.i18n import loader
from hyperadmin.i18n.loader import (
    _clear_caches,
    get_current_translations,
    gettext,
    gettext_lazy,
    install_jinja_i18n,
    load_translations,
    ngettext,
    set_current_translations,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# .mo helpers
# ---------------------------------------------------------------------------


def _write_mo(target: Path, locale: str, msgs: dict[str, str]) -> None:
    """Build a real .mo file at ``target`` for ``locale`` containing ``msgs``.

    Uses Babel's own ``Catalog`` + ``write_mo`` so the binary is fully valid
    (correct charset metadata, plural-forms header, etc.).
    """
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo

    catalog = Catalog(locale=locale, charset="utf-8")
    for msgid, msgstr in msgs.items():
        catalog.add(msgid, string=msgstr)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        write_mo(fh, catalog)


@pytest.fixture
def temp_locale_dir(tmp_path: Path) -> Iterator[Path]:
    """Build a fake locale tree under tmp_path with `es` translations and yield it."""
    es_dir = tmp_path / "es" / "LC_MESSAGES"
    _write_mo(
        es_dir / "messages.mo",
        locale="es",
        msgs={
            "Save": "Guardar",
            "Sign in": "Iniciar sesión",
        },
    )
    return tmp_path


@pytest.fixture(autouse=True)
def reset_state() -> Iterator[None]:
    """Clear LRU + warning state between tests."""
    _clear_caches()
    token = set_current_translations(babel.support.NullTranslations())
    try:
        yield
    finally:
        loader.reset_current_translations(token)
        _clear_caches()


# ---------------------------------------------------------------------------
# load_translations
# ---------------------------------------------------------------------------


class TestLoadTranslations:
    def test_missing_catalog_returns_null_translations(self) -> None:
        result = load_translations("ja")
        assert isinstance(result, babel.support.NullTranslations)
        assert not isinstance(result, babel.support.Translations)

    def test_missing_catalog_logs_warning_once(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="hyperadmin.i18n"):
            load_translations("ja")
            load_translations("ja")  # second call must not log again
        warnings = [r for r in caplog.records if "ja" in r.getMessage()]
        assert len(warnings) == 1

    def test_load_real_catalog(
        self, monkeypatch: pytest.MonkeyPatch, temp_locale_dir: Path
    ) -> None:
        monkeypatch.setattr(loader, "LOCALE_DIR", temp_locale_dir)
        _clear_caches()
        result = load_translations("es")
        assert isinstance(result, babel.support.Translations)
        assert result.gettext("Save") == "Guardar"

    def test_lru_cache_returns_same_instance(self) -> None:
        first = load_translations("en")
        second = load_translations("en")
        assert first is second


# ---------------------------------------------------------------------------
# Request-aware gettext / ngettext / gettext_lazy
# ---------------------------------------------------------------------------


class TestCurrentTranslations:
    def test_default_is_null_translations(self) -> None:
        # The autouse reset_state fixture installs NullTranslations.
        assert isinstance(get_current_translations(), babel.support.NullTranslations)
        assert gettext("Save") == "Save"

    def test_gettext_uses_active_catalog(
        self, monkeypatch: pytest.MonkeyPatch, temp_locale_dir: Path
    ) -> None:
        monkeypatch.setattr(loader, "LOCALE_DIR", temp_locale_dir)
        _clear_caches()
        translations = load_translations("es")
        token = set_current_translations(translations)
        try:
            assert gettext("Save") == "Guardar"
        finally:
            loader.reset_current_translations(token)
        # After reset, default is back
        assert gettext("Save") == "Save"

    def test_ngettext_falls_back_to_plural_msgid(self) -> None:
        # NullTranslations returns singular for n==1, plural otherwise.
        assert ngettext("{n} item", "{n} items", 1) == "{n} item"
        assert ngettext("{n} item", "{n} items", 5) == "{n} items"


class TestGettextLazy:
    def test_lazy_returns_msgid_when_no_catalog(self) -> None:
        proxy = gettext_lazy("Save")
        assert str(proxy) == "Save"

    def test_lazy_re_evaluates_on_each_use(
        self, monkeypatch: pytest.MonkeyPatch, temp_locale_dir: Path
    ) -> None:
        proxy = gettext_lazy("Save")
        assert str(proxy) == "Save"  # NullTranslations baseline

        monkeypatch.setattr(loader, "LOCALE_DIR", temp_locale_dir)
        _clear_caches()
        translations = load_translations("es")
        token = set_current_translations(translations)
        try:
            assert str(proxy) == "Guardar"
        finally:
            loader.reset_current_translations(token)
        assert str(proxy) == "Save"  # Back to baseline after token reset


# ---------------------------------------------------------------------------
# Jinja env wiring
# ---------------------------------------------------------------------------


class TestInstallJinjaI18n:
    def test_msgid_passthrough_with_no_catalog(self) -> None:
        env = Environment(autoescape=False)
        install_jinja_i18n(env)
        assert env.from_string("{{ _('Save') }}").render() == "Save"

    def test_translates_when_catalog_active(
        self, monkeypatch: pytest.MonkeyPatch, temp_locale_dir: Path
    ) -> None:
        monkeypatch.setattr(loader, "LOCALE_DIR", temp_locale_dir)
        _clear_caches()
        env = Environment(autoescape=False)
        install_jinja_i18n(env)
        translations = load_translations("es")
        token = set_current_translations(translations)
        try:
            assert env.from_string("{{ _('Save') }}").render() == "Guardar"
        finally:
            loader.reset_current_translations(token)

    def test_trans_block_works(
        self, monkeypatch: pytest.MonkeyPatch, temp_locale_dir: Path
    ) -> None:
        monkeypatch.setattr(loader, "LOCALE_DIR", temp_locale_dir)
        _clear_caches()
        env = Environment(autoescape=False)
        install_jinja_i18n(env)
        translations = load_translations("es")
        token = set_current_translations(translations)
        try:
            tmpl = env.from_string("{% trans %}Sign in{% endtrans %}")
            assert tmpl.render() == "Iniciar sesión"
        finally:
            loader.reset_current_translations(token)


# ---------------------------------------------------------------------------
# Corrupt .mo file
# ---------------------------------------------------------------------------


class TestCorruptCatalog:
    def test_load_returns_null_on_corrupt_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        bad_dir = tmp_path / "es" / "LC_MESSAGES"
        bad_dir.mkdir(parents=True)
        (bad_dir / "messages.mo").write_bytes(b"NOT_A_VALID_MO_FILE")
        monkeypatch.setattr(loader, "LOCALE_DIR", tmp_path)
        _clear_caches()
        with caplog.at_level(logging.WARNING, logger="hyperadmin.i18n"):
            result = load_translations("es")
        assert isinstance(result, babel.support.NullTranslations)
        assert not isinstance(result, babel.support.Translations)


# ---------------------------------------------------------------------------
# Patched-import sanity: gettext alias ``_`` exists in Jinja env
# ---------------------------------------------------------------------------


def test_underscore_alias_in_env() -> None:
    env = Environment(autoescape=False)
    install_jinja_i18n(env)
    # `jinja2.ext.i18n` exposes `_` as an alias for gettext on the env globals
    rendered = env.from_string("{{ _('Hello') }}").render()
    assert rendered == "Hello"


# Touch the unused `patch` import for tooling that flags it.
_ = patch
