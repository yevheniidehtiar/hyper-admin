# Views

Views are the core components of HyperAdmin that are responsible for rendering the admin interface for your models. They define how data is displayed and how users can interact with it.

## BaseView

The `BaseView` is the foundation for all views in HyperAdmin. It provides the basic structure and functionality that all other views build upon.

::: hyperadmin.views.base.BaseView

## ModelView

The `ModelView` is used to create CRUD interfaces for your data models. It automatically generates list, detail, create, and update views.

::: hyperadmin.views.model.ModelView

## AdminView

The `AdminView` is a view that is not tied to a specific model. It can be used to create custom pages in your admin interface.

::: hyperadmin.views.admin.AdminView