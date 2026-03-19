# Views

## ModelView class attributes

When subclassing `ModelView`, these class-level attributes control the generated admin UI:

| Attribute | Type | Description |
|-----------|------|-------------|
| `column_list` | `list` | Fields shown as columns in the list view |
| `column_details_list` | `list` | Fields shown on the detail page |
| `column_searchable_list` | `list` | Fields searched when using the search box |
| `column_sortable_list` | `list` | Fields that render a sort link in the list header |
| `column_filters` | `list` | Fields available as filter dropdowns |
| `form_columns` | `list` | Fields included in create/edit forms |
| `icon` | `str` | Sidebar icon name (from the icon set) |
| `name_plural` | `str` | Human-readable plural name shown in the sidebar |

Example:

```python
from hyperadmin.views.dynamic import ModelView
from myapp.models import User

class UserAdmin(ModelView, model=User):
    column_list = [User.username, User.email, User.is_active]
    column_searchable_list = [User.username, User.email]
    column_sortable_list = [User.username, User.created_at]
    form_columns = [User.username, User.email, User.first_name, User.last_name]
    icon = "person"
    name_plural = "Users"
```

## DynamicModelView

The `DynamicModelView` handles all CRUD views for a registered model: list, detail, create, and update. Routes are generated automatically by `HyperAdminRouter`.

::: hyperadmin.views.dynamic.DynamicModelView

## PydanticForm

`PydanticForm` binds a Pydantic/SQLModel class to a set of widgets, validates submitted data, and collects field-level errors for re-rendering.

::: hyperadmin.views.forms.PydanticForm

## HtmxWidget

The base widget class. Pairs a Jinja2 template with optional HTMX attributes and static assets.

::: hyperadmin.views.forms.HtmxWidget