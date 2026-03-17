# Views

Views are the core components of HyperAdmin that are responsible for rendering the admin interface for your models. They define how data is displayed and how users can interact with it.

## DynamicModelView

The `DynamicModelView` handles all CRUD views for a registered model: list, detail, create, and update. Routes are generated automatically by `HyperAdminRouter`.

::: hyperadmin.views.dynamic.DynamicModelView

## PydanticForm

`PydanticForm` binds a Pydantic/SQLModel class to a set of widgets, validates submitted data, and collects field-level errors for re-rendering.

::: hyperadmin.views.forms.PydanticForm

## HtmxWidget

The base widget class. Pairs a Jinja2 template with optional HTMX attributes and static assets.

::: hyperadmin.views.forms.HtmxWidget