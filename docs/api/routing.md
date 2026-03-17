# Routing

The routing system in HyperAdmin is responsible for mapping URLs to your admin views. It is built on top of FastAPI's routing layer, providing a flexible and powerful way to define your admin URLs.

## HyperAdminRouter

The `HyperAdminRouter` is the core of the routing system. It generates FastAPI routes for all registered models and mounts them on the admin application.

::: hyperadmin.routing.HyperAdminRouter