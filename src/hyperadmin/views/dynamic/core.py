"""``DynamicModelView``: the per-model CRUD view, composed from the handler mixins."""

from fastapi import Request
from fastapi.templating import Jinja2Templates

from hyperadmin.views.dynamic.actions import ActionViewMixin
from hyperadmin.views.dynamic.create import CreateViewMixin
from hyperadmin.views.dynamic.detail import DetailViewMixin
from hyperadmin.views.dynamic.list_view import ListViewMixin
from hyperadmin.views.dynamic.update import UpdateViewMixin


class DynamicModelView(
    ListViewMixin,
    DetailViewMixin,
    CreateViewMixin,
    UpdateViewMixin,
    ActionViewMixin,
):
    """View handler that serves all CRUD endpoints for a registered model.

    One instance is created per model by ``HyperAdminRouter``. It delegates
    all database operations to its ``adapter`` and renders Jinja2 templates
    resolved through the template-search hierarchy.
    """


async def admin_dashboard(request: Request, templates: Jinja2Templates):
    """Renders the main admin dashboard page."""
    context = {"request": request}
    return templates.TemplateResponse(request, "dashboard.html", context)
