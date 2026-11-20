"""Operator settings of the reports plugin (``HYPERADMIN_REPORTS_*`` environment variables).

Supplied as ``Admin(..., plugin_settings={"reports": {...}})`` or through the
environment; the plugin registry validates them into :class:`ReportsSettings`
before ``ReportsPlugin.on_register`` runs.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: What ``PluginRegistry.add_page`` accepts as a page prefix.
PAGE_PREFIX_PATTERN = r"^(/[a-z0-9][a-z0-9_-]*)+$"


class ReportsSettings(BaseSettings):
    """Validated settings; the plugin registry builds one as ``ReportsPlugin.settings_model``."""

    model_config = SettingsConfigDict(env_prefix="HYPERADMIN_REPORTS_", extra="ignore")

    #: Serve the dashboard at the admin index ``{prefix}/`` (when widgets are registered).
    dashboard_home: bool = True
    #: Remember each user's widget order. ``False``: default order, no reorder
    #: controls, no access to the layout table and no warning about it.
    dashboard_layouts: bool = True
    #: Admin-relative prefix of the dashboard page; rename it when a model slug is ``dashboard``.
    dashboard_prefix: str = Field(default="/dashboard", pattern=PAGE_PREFIX_PATTERN)
