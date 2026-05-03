from __future__ import annotations

from pydantic import BaseModel, Field

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
    list_display: list[str] | None = None
    """Field names to show in the list view table.

    - ``None`` (default): smart defaults via ``infer_list_display()``.
    - ``[]``: empty — no columns shown (disables feature).
    - ``["id", "name"]``: explicit list used as-is.
    """
    search_fields: list[str] | None = None
    """Field names to include in full-text search.

    - ``None`` (default): smart defaults via ``infer_search_fields()``.
    - ``[]``: search disabled.
    - ``["name", "email"]``: explicit list used as-is.
    """
    list_filter: list[str] | None = None
    """List of field names to show in the filter bar.

    - ``None`` (default): smart defaults via ``infer_list_filter()``.
    - ``[]``: filtering disabled.
    - ``["is_active", "status"]``: explicit list used as-is.
    """
    list_editable: list[str] = Field(default_factory=list)
    """Allow-list of field names that can be inline-edited in the list view.

    Empty by default — feature is opt-in. Fields named here MUST exist on the
    model schema. The primary key (``id``) is never inline-editable, even if
    listed here, and is filtered out at the view layer.
    """
    dependent_fields: dict[str, str] = {}
    """Cascading select configuration: maps child field name → parent field name.

    Example: ``{"city": "country_id"}`` makes the city select reload when country_id changes.
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
