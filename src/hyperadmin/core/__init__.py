"""Core components for HyperAdmin."""

from hyperadmin.core.actions import ActionDef, action, collect_actions
from hyperadmin.core.adapters import JsonApiAdapter, ListEnvelope, PaginationMeta
from hyperadmin.core.auth import (
    AdminAccessDenied,
    AdminAuthenticationRequired,
    DefaultObjectPermissionChecker,
    ObjectPermissionChecker,
)
from hyperadmin.core.choices import ChoiceItem, ChoicesProvider, SelectFieldMeta
from hyperadmin.core.display import get_field_label
from hyperadmin.core.fields import classify_field
from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.filtering import FilterCondition, FilterValueError
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.introspection import (
    FieldMeta,
    discover_sqlmodel_models,
    get_field_metadata,
    infer_list_display,
    infer_list_filter,
    infer_search_fields,
)
from hyperadmin.core.layouts import FormLayout
from hyperadmin.core.primary_key import DEFAULT_PK, InvalidPrimaryKey, PrimaryKeyInfo
from hyperadmin.core.timezones import utc_now

__all__ = [
    "DEFAULT_PK",
    "ActionDef",
    "AdminAccessDenied",
    "AdminAuthenticationRequired",
    "ChoiceItem",
    "ChoicesProvider",
    "DefaultObjectPermissionChecker",
    "FieldMeta",
    "FieldsetSpec",
    "FilterCondition",
    "FilterValueError",
    "FormLayout",
    "InlineModelSpec",
    "InvalidPrimaryKey",
    "JsonApiAdapter",
    "ListEnvelope",
    "ObjectPermissionChecker",
    "PaginationMeta",
    "PrimaryKeyInfo",
    "SelectFieldMeta",
    "action",
    "classify_field",
    "collect_actions",
    "discover_sqlmodel_models",
    "get_field_label",
    "get_field_metadata",
    "infer_list_display",
    "infer_list_filter",
    "infer_search_fields",
    "utc_now",
]
