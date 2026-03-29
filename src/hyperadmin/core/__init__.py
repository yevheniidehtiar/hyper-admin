"""Core components for HyperAdmin."""

from hyperadmin.core.actions import ActionDef, action, collect_actions
from hyperadmin.core.adapters import JsonApiAdapter, ListEnvelope, PaginationMeta
from hyperadmin.core.choices import ChoiceItem, ChoicesProvider, SelectFieldMeta
from hyperadmin.core.fields import classify_field
from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.layouts import FormLayout

__all__ = [
    "ActionDef",
    "ChoiceItem",
    "ChoicesProvider",
    "FieldsetSpec",
    "FormLayout",
    "InlineModelSpec",
    "JsonApiAdapter",
    "ListEnvelope",
    "PaginationMeta",
    "SelectFieldMeta",
    "action",
    "classify_field",
    "collect_actions",
]
