from importlib.metadata import version as _distribution_version

from hyperadmin.core.app import Admin
from hyperadmin.core.concurrency import ConcurrencyConfigurationError, StaleRecordError
from hyperadmin.core.navigation import NavGroup
from hyperadmin.core.plugins import Plugin, PluginError, PluginRegistry
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n import gettext_lazy
from hyperadmin.panels import PDFStreamPanel, pdf_stream_panel
from hyperadmin.realtime import RealtimeSettings

# The distribution is ``hyper-admin``; the import name is ``hyperadmin``.
__version__: str = _distribution_version("hyper-admin")

__all__ = [
    "Admin",
    "ConcurrencyConfigurationError",
    "HyperAdminSettings",
    "NavGroup",
    "PDFStreamPanel",
    "Plugin",
    "PluginError",
    "PluginRegistry",
    "RealtimeSettings",
    "StaleRecordError",
    "__version__",
    "gettext_lazy",
    "pdf_stream_panel",
]

# OAuth sign-in (docs/specs/oauth-sso.md) is opt-in and needs the ``oauth`` extra, so
# its names resolve on first access (PEP 562) and ``import hyperadmin`` never loads it.
# They stay out of ``__all__``: a star import must not load the built-in auth models.
_OAUTH_EXPORTS = frozenset(
    {
        "AccountLinkRequiredError",
        "OAuthBackend",
        "OAuthProviderConfig",
        "OAuthProviderError",
        "github_provider",
        "google_provider",
    }
)


def __getattr__(name: str) -> object:
    if name not in _OAUTH_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    from hyperadmin.auth import oauth  # noqa: PLC0415 - lazy: needs the oauth extra

    return getattr(oauth, name)
