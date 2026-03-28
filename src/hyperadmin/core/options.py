from __future__ import annotations

from pydantic import BaseModel

from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.layouts import FormLayout


class AdminOptions(BaseModel):
    """Per-model configuration for the HyperAdmin interface.

    Pass an instance to ``site.register()`` or set it as a class attribute on
    a ``ModelView`` subclass to control which views are generated.

    Example:
        ```python
        from hyperadmin.core.options import AdminOptions
        from hyperadmin.core.registry import site

        site.register(Product, options=AdminOptions(can_delete=False))
        ```
    """

    can_create: bool = True
    """Whether the Create form and POST endpoint are generated."""
    can_edit: bool = True
    """Whether the Edit form and PUT endpoint are generated."""
    can_delete: bool = True
    """Whether the Delete action and DELETE endpoint are generated."""
    can_list: bool = True
    """Whether the List view and GET (collection) endpoint are generated."""
    can_detail: bool = True
    """Whether the Detail view and GET (single item) endpoint are generated."""
    list_filter: list[str] = []
    """List of field names to show in the filter bar."""
    dependent_fields: dict[str, str] = {}
    """Cascading select configuration: maps child field name → parent field name.

    Example: ``{"city": "country_id"}`` makes the city select reload when country_id changes.
    """
    fieldsets: list[FieldsetSpec] = []
    """Groups of fields rendered together under collapsible headings in create/update forms.

    When non-empty, the form renders fields in the order defined by the fieldsets.
    Fields not included in any fieldset are rendered in a default ungrouped section.

    Example:
        ```python
        AdminOptions(fieldsets=[
            FieldsetSpec(name="Basic Info", fields=["name", "email"]),
            FieldsetSpec(name="Advanced", fields=["is_active", "rating"], collapsed=True),
        ])
        ```
    """
    form_layout: FormLayout = FormLayout.SINGLE
    """Controls the column layout of form fields.

    - ``FormLayout.SINGLE``: One field per row (default).
    - ``FormLayout.TWO_COLUMN``: Fields arranged in a two-column grid.

    Example:
        ```python
        AdminOptions(form_layout=FormLayout.TWO_COLUMN)
        ```
    """
    form_fields: list[str] = []
    """Explicit ordering of fields in create/update forms.

    When non-empty, only these fields are shown, in the specified order.
    When empty, all editable fields are shown in model-definition order.

    Example:
        ```python
        AdminOptions(form_fields=["name", "email", "is_active"])
        ```
    """
    inlines: list[InlineModelSpec] = []
    """Inline related models rendered as sub-forms within create/update views.

    Each ``InlineModelSpec`` defines a related model whose rows can be added,
    edited, and removed directly in the parent form.

    Example:
        ```python
        AdminOptions(inlines=[
            InlineModelSpec(model=OrderItem, fk_field="order_id", extra=3),
        ])
        ```
    """
