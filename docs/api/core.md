# Core Components

The core components of HyperAdmin provide the foundational building blocks for creating admin interfaces. These components are responsible for handling the main logic of the admin panel.

## Admin

The `Admin` class is the main entry point for creating an admin interface. It is responsible for managing admin views, handling requests, and rendering templates.

::: hyperadmin.core.admin.Admin

## AdminSite

The `AdminSite` class is a container for admin views. It is used to group related views together and provides a way to register and unregister views.

::: hyperadmin.core.sites.AdminSite