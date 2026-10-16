"""ModelAdmin registrations for the field/widget showcase.

Note on ``list_display`` / ``search_fields``: unlike ``list_filter`` and
``list_editable`` (which ``core/registry.py`` and ``routing.py`` merge from a
bare class attribute), ``list_display`` and ``search_fields`` are **only**
read from ``AdminOptions`` (see ``routing.py::_resolve_smart_defaults``). A
bare ``list_display: ClassVar[...] = [...]`` on a ``ModelAdmin`` subclass —
the pattern used throughout ``examples/erp/{contacts,sales,purchases,
accounting}/admin.py`` — is silently ignored; those apps are actually showing
the *inferred* smart-default columns, not the ones written in their
``admin.py`` files. See the PR description for the full writeup; this module
deliberately uses the working ``AdminOptions(list_display=..., search_fields=...)``
form instead of copying that dead pattern.
"""

from __future__ import annotations

from typing import ClassVar

from examples.erp.showcase.models import FieldShowcase, ShowcaseCategory, ShowcaseSubcategory
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.layouts import FormLayout
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions, RelationDependency
from hyperadmin.core.registry import site


class ShowcaseCategoryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    verbose_name_plural = "Showcase Categories"
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=["id", "name"],
        search_fields=["name"],
    )


class ShowcaseSubcategoryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    verbose_name_plural = "Showcase Subcategories"
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=["id", "name", "category"],
        list_filter=["category_id"],
        search_fields=["name"],
    )


class FieldShowcaseAdmin(ModelAdmin):
    """Demonstrates every HyperAdmin field widget. See showcase/models.py.

    ``dependent_fields`` / ``relation_filters`` are set below to document the
    cascading-select config surface (``AdminOptions``), but — per the module
    docstring in ``showcase/models.py`` — the auto-detected widget for a
    scalar FK column always resolves ``preload=True``, and the
    ``relation_select_input.html`` template only honours ``dependent_on``
    on the ``preload=False`` branch. So this config is exercised by
    ``AdminOptions.validate_against_model`` (it would raise if the field name
    were wrong) but has no visible cascading effect in the rendered page —
    see the PR description.
    """

    adapter_class = SQLModelAdapter
    verbose_name = "Field Showcase Item"
    verbose_name_plural = "Field Showcase Items"
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=[
            "id",
            "name",
            "priority",
            "is_active",
            "unit_price",
            "quantity_in_stock",
            "category",
            "launched_at",
        ],
        list_filter=["priority", "is_active"],
        search_fields=["name"],
        list_editable=["is_active", "priority"],
        form_layout=FormLayout.TWO_COLUMN,
        fieldsets=[
            FieldsetSpec(name="Identity", fields=["name", "description", "is_active"]),
            FieldsetSpec(
                name="Attributes",
                fields=["priority", "tags", "quantity_in_stock", "unit_price", "launched_at"],
            ),
            FieldsetSpec(
                name="Media",
                fields=["manual_file", "photo"],
                description="FileInputWidget demos: a generic file and an image.",
            ),
            FieldsetSpec(
                name="Relations",
                fields=["category_id", "subcategory_id", "supplier_id"],
                description="RelationSelectWidget demos: three preloaded foreign keys.",
            ),
        ],
        dependent_fields={"subcategory_id": "category_id"},
        relation_filters={
            "subcategory_id": RelationDependency(
                depends_on="category_id",
                placeholder="Pick a category first",
            ),
        },
    )


site.register(ShowcaseCategory, ShowcaseCategoryAdmin)
site.register(ShowcaseSubcategory, ShowcaseSubcategoryAdmin)
site.register(FieldShowcase, FieldShowcaseAdmin)
