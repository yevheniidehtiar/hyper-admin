# Routing

The routing system in HyperAdmin is responsible for mapping URLs to your admin views. It is built on top of FastAPI's routing layer, providing a flexible and powerful way to define your admin URLs.

## AdminAPIRouter

The `AdminAPIRouter` is the core of the routing system. It is a subclass of `fastapi.APIRouter` and provides additional functionality for discovering and registering admin views.

::: hyperadmin.routing.AdminAPIRouter