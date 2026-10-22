"""Dynamic CRUD views, split into cohesive modules.

``DynamicModelView`` is composed from the handler mixins in the sibling modules;
the names that used to live in the single ``hyperadmin.views.dynamic`` module are
re-exported here.
"""

from hyperadmin.views.dynamic.core import DynamicModelView, admin_dashboard
from hyperadmin.views.dynamic.helpers import (
    LIST_BODY_ID,
    _as_attachment,
    _discard_stream,
    _disposition_filename,
    _human_size,
    _integrity_error_to_field_errors,
    _is_missing_table_error,
    _ListFilters,
    _request_scoped,
)
from hyperadmin.views.dynamic.model_view import ModelView

__all__ = [
    "LIST_BODY_ID",
    "DynamicModelView",
    "ModelView",
    "_ListFilters",
    "_as_attachment",
    "_discard_stream",
    "_disposition_filename",
    "_human_size",
    "_integrity_error_to_field_errors",
    "_is_missing_table_error",
    "_request_scoped",
    "admin_dashboard",
]
