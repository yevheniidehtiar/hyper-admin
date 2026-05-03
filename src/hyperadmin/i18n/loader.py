"""gettext catalog loader and lazy proxy for HyperAdmin.

Exposes:

- :func:`load_translations` -- load a ``babel.support.Translations`` for a
  locale, with LRU caching and graceful fallback to ``NullTranslations``.
- :func:`gettext`, :func:`ngettext` -- callables bound on the Jinja env
  that look up the current request's translations via a context var.
- :func:`gettext_lazy` -- lazy string proxy used for class-body model
  metadata (e.g. ``verbose_name = gettext_lazy("User")`` in C2-E).
- :func:`set_current_translations` -- middleware hook to install the active
  catalog for the duration of a request.

Catalogs live at ``src/hyperadmin/locale/<locale>/LC_MESSAGES/messages.mo``
(seeded by C3-C). Missing catalogs are handled with a single warning per
locale per process so the application never crashes on a half-translated
deployment.
"""

from __future__ import annotations

import contextvars
import functools
import logging
from pathlib import Path

import babel.support

log = logging.getLogger("hyperadmin.i18n")

LOCALE_DIR: Path = Path(__file__).resolve().parent.parent / "locale"
DOMAIN = "messages"

_warned_missing: set[str] = set()

_current_translations: contextvars.ContextVar[babel.support.NullTranslations] = (
    contextvars.ContextVar("hyperadmin_translations", default=babel.support.NullTranslations())
)


@functools.lru_cache(maxsize=32)
def load_translations(locale: str) -> babel.support.NullTranslations:
    """Return the gettext catalog for ``locale``.

    Returns a :class:`babel.support.Translations` when the ``.mo`` file is
    present, otherwise a :class:`babel.support.NullTranslations` (which is
    a safe identity translator). The first time a missing catalog is
    requested for a given locale, a WARNING is logged.
    """
    try:
        result = babel.support.Translations.load(
            dirname=str(LOCALE_DIR),
            locales=[locale],
            domain=DOMAIN,
        )
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("Failed to load translation catalog for %r: %s", locale, exc)
        return babel.support.NullTranslations()

    if not isinstance(result, babel.support.Translations):
        if locale not in _warned_missing:
            log.warning("No translation catalog for locale %r; using msgid passthrough", locale)
            _warned_missing.add(locale)
    return result


def set_current_translations(
    translations: babel.support.NullTranslations,
) -> contextvars.Token[babel.support.NullTranslations]:
    """Install ``translations`` as the active catalog for this context.

    Returns the contextvar token; pass it to :func:`reset_current_translations`
    to restore the previous value.
    """
    return _current_translations.set(translations)


def reset_current_translations(
    token: contextvars.Token[babel.support.NullTranslations],
) -> None:
    """Restore the previous catalog using the token from :func:`set_current_translations`."""
    _current_translations.reset(token)


def get_current_translations() -> babel.support.NullTranslations:
    """Return the currently-installed catalog (NullTranslations outside a request)."""
    return _current_translations.get()


def gettext(message: str) -> str:
    """Translate ``message`` using the current request's catalog."""
    return _current_translations.get().gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Translate plural-form ``singular``/``plural`` for count ``n``."""
    return _current_translations.get().ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    """Translate ``message`` in a disambiguating ``context``."""
    result = _current_translations.get().pgettext(context, message)
    return str(result)


def gettext_lazy(message: str) -> babel.support.LazyProxy:
    """Return a lazy proxy that translates ``message`` on each ``str(...)`` call.

    Required for class-body strings (model ``verbose_name``, field labels)
    where evaluation must defer until a request is active. ``enable_cache=False``
    so the proxy re-translates every render -- otherwise the first locale wins.
    """
    return babel.support.LazyProxy(lambda: gettext(message), enable_cache=False)


def install_jinja_i18n(env) -> None:  # type: ignore[no-untyped-def]
    """Wire ``jinja2.ext.i18n`` and the request-aware gettext callables onto ``env``.

    Call once during ``Admin.__init__``. Per-request translations are picked up
    automatically because the gettext callables read from a context var that
    :class:`hyperadmin.i18n.middleware.LocaleMiddleware` populates.
    """
    env.add_extension("jinja2.ext.i18n")
    env.install_gettext_callables(gettext, ngettext, newstyle=True)
    env.globals.setdefault("ngettext", ngettext)
    env.globals.setdefault("pgettext", pgettext)


# Re-exported for tests that need to clear caches between cases.
def _clear_caches() -> None:
    """Reset the per-process LRU cache and warning registry. Test-only."""
    load_translations.cache_clear()
    _warned_missing.clear()


__all__ = [
    "DOMAIN",
    "LOCALE_DIR",
    "_clear_caches",
    "get_current_translations",
    "gettext",
    "gettext_lazy",
    "install_jinja_i18n",
    "load_translations",
    "ngettext",
    "pgettext",
    "reset_current_translations",
    "set_current_translations",
]
