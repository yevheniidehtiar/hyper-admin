from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hyperadmin.core.auth import ObjectPermissionChecker
from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.layouts import FormLayout


class RelationDependency(BaseModel):
    """Declarative cascading-select wiring for a FK/M2M autocomplete widget.

    See ``docs/specs/htmx-autocomplete.md``. When set on
    :class:`AdminOptions.relation_filters`, the widget for the keyed child
    field forwards ``depends_on``'s current value via ``hx-include`` so that
    its options narrow against the parent's selection.

    Args:
        depends_on: Name of the parent field on the same form. Validated
            against the bound model via :meth:`AdminOptions.validate_against_model`.
        placeholder: Hint shown when the parent has no value yet.
    """

    model_config = ConfigDict(extra="forbid")

    depends_on: str
    placeholder: str | None = None


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    object_permission_checker: ObjectPermissionChecker | None = None
    """Per-object permission checker used by the view layer for fine-grained authz.

    When ``None`` (default), no object-level checks are performed and behavior
    matches model-level :class:`PermissionChecker` enforcement only. Provide a
    custom :class:`ObjectPermissionChecker` (or
    :class:`DefaultObjectPermissionChecker` as a permissive baseline) to opt
    into per-object authorization.

    The view layer that consumes this field is wired in a later slot (C2-C);
    declaring it here lets model registrations adopt object-level checks ahead
    of the wiring.
    """
    relation_filters: dict[str, RelationDependency] | None = None
    """Declarative dependent-filtering for FK/M2M autocomplete widgets.

    Keys are child field names; values describe which parent field on the
    same form the child depends on. The widget for each keyed child
    forwards the parent's value via ``hx-include`` so the dropdown narrows
    automatically. See ``docs/specs/htmx-autocomplete.md``.

    Example:
        ```python
        AdminOptions(
            relation_filters={
                "variant_id": RelationDependency(depends_on="supplier_id"),
            }
        )
        ```
    """
    relation_display: dict[str, str | Callable[[Any], str]] | None = None
    """Per-relation option-label rendering.

    Maps a FK/M2M field name to either a Python format string or a callable
    that receives the related instance and returns its display label. Format
    strings are the recommended path; callables are an escape hatch for
    computed properties unreachable via ``getattr``.

    Example:
        ```python
        AdminOptions(relation_display={"supplier_id": "{name} — {city}"})
        ```
    """
    use_autocomplete_widget: bool = True
    """Whether FK/M2M fields render via :class:`AutocompleteWidget`.

    Defaults to ``True``: the new widget is a strict superset of the legacy
    ``<select>`` rendering. Set to ``False`` to opt back into the legacy
    widget on a per-model basis.
    """

    def validate_against_model(self, model: type) -> None:
        """Validate options that reference field names against a concrete model.

        Called by the registry when the options are bound to ``model``. Raises
        :class:`ValueError` if any ``relation_filters[child].depends_on``
        references a field that does not exist on the model.

        Args:
            model: The SQLModel / Pydantic class these options are bound to.

        Raises:
            ValueError: If a referenced field name does not exist on the model.
        """
        if not self.relation_filters:
            return

        field_names = set(getattr(model, "model_fields", {}).keys()) | {
            attr for attr in dir(model) if not attr.startswith("_")
        }
        for child, dep in self.relation_filters.items():
            if dep.depends_on not in field_names:
                raise ValueError(
                    f"relation_filters[{child!r}].depends_on={dep.depends_on!r} "
                    f"not in form fields of {model.__name__}"
                )
