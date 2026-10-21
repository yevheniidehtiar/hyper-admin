from importlib.metadata import version as _distribution_version

from hyperadmin.core.app import Admin
from hyperadmin.core.plugins import Plugin, PluginError, PluginRegistry
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n import gettext_lazy
from hyperadmin.panels import PDFStreamPanel, pdf_stream_panel
from hyperadmin.realtime import RealtimeSettings

# The distribution is ``hyper-admin``; the import name is ``hyperadmin``.
__version__: str = _distribution_version("hyper-admin")

__all__ = [
    "Admin",
    "HyperAdminSettings",
    "PDFStreamPanel",
    "Plugin",
    "PluginError",
    "PluginRegistry",
    "RealtimeSettings",
    "__version__",
    "gettext_lazy",
    "pdf_stream_panel",
]
