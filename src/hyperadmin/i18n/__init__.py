"""Internationalization (i18n) primitives for HyperAdmin.

Provides:

- :class:`LocaleMiddleware` -- per-request locale resolution
  (cookie > Accept-Language > settings default).
- :func:`negotiate_locale` -- pure-function locale resolver, exposed for testing
  and reuse outside the middleware.
- :func:`load_translations` -- load a Babel ``Translations`` for a locale.
- :func:`gettext`, :func:`ngettext`, :func:`pgettext` -- request-aware
  translation callables (read the active catalog from a context var).
- :func:`gettext_lazy` -- lazy proxy used for class-body model metadata.
- :func:`install_jinja_i18n` -- wire ``jinja2.ext.i18n`` + the gettext
  callables onto a Jinja environment.
"""

from __future__ import annotations

from hyperadmin.i18n.loader import (
    get_current_translations,
    gettext,
    gettext_lazy,
    install_jinja_i18n,
    load_translations,
    ngettext,
    pgettext,
    reset_current_translations,
    set_current_translations,
)
from hyperadmin.i18n.middleware import RTL_LOCALES, LocaleMiddleware, negotiate_locale

__all__ = [
    "RTL_LOCALES",
    "LocaleMiddleware",
    "get_current_translations",
    "gettext",
    "gettext_lazy",
    "install_jinja_i18n",
    "load_translations",
    "negotiate_locale",
    "ngettext",
    "pgettext",
    "reset_current_translations",
    "set_current_translations",
]
