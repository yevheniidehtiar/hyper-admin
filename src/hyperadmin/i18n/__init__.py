"""Internationalization (i18n) primitives for HyperAdmin.

Provides:

- :class:`LocaleMiddleware` -- per-request locale resolution
  (cookie > Accept-Language > settings default).
- :func:`negotiate_locale` -- pure-function locale resolver, exposed for testing
  and reuse outside the middleware.
"""

from __future__ import annotations

from hyperadmin.i18n.middleware import LocaleMiddleware, negotiate_locale

__all__ = ["LocaleMiddleware", "negotiate_locale"]
