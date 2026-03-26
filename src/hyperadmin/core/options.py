from pydantic import BaseModel


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
