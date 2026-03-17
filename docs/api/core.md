# Core Components

The core components of HyperAdmin provide the foundational building blocks for creating admin interfaces. These components are responsible for handling the main logic of the admin panel.

## Admin

The `Admin` class is the main entry point for creating an admin interface. It is responsible for managing admin views, handling requests, and rendering templates.

::: hyperadmin.core.app.Admin

## SiteRegistry

The `SiteRegistry` class is a container for registered admin models. It maintains the mapping between models and their admin options.

::: hyperadmin.core.registry.SiteRegistry