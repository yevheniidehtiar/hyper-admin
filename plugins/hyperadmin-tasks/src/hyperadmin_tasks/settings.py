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
    #: Whether ``hyperadmin_tasks.lifespan(admin)`` runs a pgtask worker inside the admin process.
    run_worker: bool = False
    #: Worker-role connection string for the in-process worker; falls back to ``dsn``.
    worker_dsn: str | None = None
    #: ``"module:attr"`` path to the pgtask ``TaskRegistry`` (or a list of them) the worker runs.
    registries: str | None = None
    #: Handlers the in-process worker runs at once.
    worker_concurrency: int = 10
    #: Seconds running handlers get to finish on shutdown before they are cancelled.
    worker_shutdown_grace: float = 30.0
