"""Entry point the HyperAdmin plugin loader discovers (``hyperadmin.plugins`` group).

Registration contributes the plugin templates (``tasks/...``), the dashboard page under
``{prefix}/tasks``, a "Tasks" sidebar entry and the ``view_tasks`` / ``manage_tasks``
permission codenames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from hyperadmin_tasks.lifecycle import BackendLifecycle
from hyperadmin_tasks.routes import VIEW_PERMISSION, build_router
from hyperadmin_tasks.selection import select_backend
from hyperadmin_tasks.settings import TasksSettings

TEMPLATES_DIR = Path(__file__).parent / "templates"
#: Admin-relative prefix of the task pages.
PAGE_PREFIX = "/tasks"
#: Sidebar section the task links live in.
NAV_SECTION = "Tasks"
#: Permission to act on tasks, queues and schedules.
MANAGE_PERMISSION = "manage_tasks"


class TasksPlugin:
    """The ``tasks`` plugin: a background task queue dashboard for HyperAdmin."""

    name: ClassVar[str] = "tasks"
    settings_model: ClassVar[type[TasksSettings]] = TasksSettings

    #: Backend lifecycle routes and :func:`hyperadmin_tasks.lifespan` go through; set on register.
    lifecycle: BackendLifecycle

    def on_register(self, admin: Any) -> None:
        """Build the backend, then contribute templates, the page, the nav entry, permissions.

        Raises ``TasksBackendError`` when the configured backend cannot be built; the plugin
        registry then logs it and skips the plugin.
        """
        plugins = admin.plugins
        settings: TasksSettings = plugins.settings(self.name) or TasksSettings()
        self.lifecycle = BackendLifecycle(select_backend(settings))
        plugins.add_template_dir(self, TEMPLATES_DIR)
        plugins.add_page(self, build_router(admin, self.lifecycle, settings), prefix=PAGE_PREFIX)
        plugins.add_nav_entry(
            self,
            label="Dashboard",
            url_name="tasks-dashboard",
            icon="list-checks",
            permission=VIEW_PERMISSION,
            section=NAV_SECTION,
            testid="nav-tasks-dashboard",
        )
        plugins.add_permission(self, VIEW_PERMISSION, name="Can view tasks")
        plugins.add_permission(self, MANAGE_PERMISSION, name="Can manage tasks")
