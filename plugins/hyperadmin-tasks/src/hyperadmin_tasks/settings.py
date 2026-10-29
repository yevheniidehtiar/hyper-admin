"""Operator settings of the tasks plugin (``HYPERADMIN_TASKS_*`` environment variables)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TasksSettings(BaseSettings):
    """Validated settings; the plugin registry builds one as ``TasksPlugin.settings_model``."""

    model_config = SettingsConfigDict(env_prefix="HYPERADMIN_TASKS_", extra="ignore")

    #: ``"memory"``, ``"pgtask"`` or a ``"module:attr"`` path to a backend factory.
    backend: str = "memory"
    #: Connection string handed to the backend (administrator role for pgtask).
    dsn: str | None = None
    #: Read-only connection string for observer views; falls back to ``dsn``.
    observer_dsn: str | None = None
    #: Dashboard auto-refresh interval in seconds; ``0`` disables it.
    refresh_seconds: int = 5
    #: Rows per page in task listings.
    page_size: int = 50
    #: Whether the host runs a worker inside the admin process.
    run_worker: bool = False
