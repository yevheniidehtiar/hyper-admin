"""Apply the plugin registry's collected UI seams to an admin (SDD ``plugin-registry``, phase 1b).

``core/plugins.py`` collects what plugins contribute; ``Admin.mount()`` calls these
helpers to apply it: plugin routes are rebuilt on the admin's route class, static
dirs are mounted, the Jinja loader is extended and sidebar entries are resolved.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.staticfiles import StaticFiles
from jinja2 import ChoiceLoader, FileSystemLoader
from starlette.routing import NoMatchFound

from hyperadmin.core.plugins import PluginError

if TYPE_CHECKING:
    from collections.abc import Collection

    from jinja2 import Environment
    from starlette.routing import BaseRoute, Router
    from starlette.types import ASGIApp

    from hyperadmin.core.plugins import PluginPage, PluginPermission, PluginRegistry

logger = logging.getLogger(__name__)


def extend_template_loader(env: Environment, registry: PluginRegistry) -> None:
    """Search plugin template dirs after the host and core templates (plugins never override)."""
    dirs = [str(template_dir.path) for template_dir in registry.template_dirs]
    if not dirs:
        return
    if isinstance(env.loader, FileSystemLoader):
        # Extended in place: views read ``loader.searchpath`` to locate templates.
        env.loader.searchpath.extend(dirs)
        return
    loaders = [loader for loader in (env.loader, FileSystemLoader(dirs)) if loader is not None]
    env.loader = ChoiceLoader(loaders)


def mount_plugin_static(target: Any, registry: PluginRegistry) -> None:
    """Mount each plugin static dir at ``/static/plugins/<name>`` on ``target``.

    Call it before the core ``/static`` mount, so the more specific path wins and
    ``url_for('static', path='/plugins/<name>/...')`` is served from the plugin dir.
    """
    for static_dir in registry.static_dirs:
        app: ASGIApp = StaticFiles(directory=static_dir.path)
        target.mount(static_dir.mount_path, app, name=f"plugin-static-{static_dir.plugin}")


def _copy_route(target: APIRouter, route: BaseRoute, prefix: str) -> None:
    """Re-add ``route`` under ``prefix`` so it is built with ``target.route_class``.

    ``include_router`` keeps each route's own class; rebuilding is what gives a plain
    plugin ``APIRouter`` the admin's ``HyperAdminRoute`` (auth bridge, CSRF, error pages).
    """
    if isinstance(route, APIRoute):
        target.add_api_route(
            prefix + route.path,
            route.endpoint,
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            methods=route.methods,
            operation_id=route.operation_id,
            response_model_include=route.response_model_include,
            response_model_exclude=route.response_model_exclude,
            response_model_by_alias=route.response_model_by_alias,
            response_model_exclude_unset=route.response_model_exclude_unset,
            response_model_exclude_defaults=route.response_model_exclude_defaults,
            response_model_exclude_none=route.response_model_exclude_none,
            include_in_schema=route.include_in_schema,
            response_class=route.response_class,
            name=route.name,
            callbacks=route.callbacks,
            openapi_extra=route.openapi_extra,
        )
    elif isinstance(route, APIWebSocketRoute):
        target.add_api_websocket_route(
            prefix + route.path, route.endpoint, name=route.name, dependencies=route.dependencies
        )
    else:
        raise PluginError(
            f"{route!r} is not supported: declare plugin routes directly on the page router "
            "(no nested include_router or mounts)"
        )


def _page_routes(page: PluginPage, route_class: type[APIRoute]) -> list[BaseRoute]:
    rebuilt = APIRouter(route_class=route_class)
    for route in page.router.routes:
        _copy_route(rebuilt, route, page.prefix)
    return rebuilt.routes


def build_plugin_routes(
    registry: PluginRegistry, *, route_class: type[APIRoute], reserved: Collection[str]
) -> list[BaseRoute]:
    """Return every plugin page's routes, rebuilt on ``route_class`` under the page prefix.

    A page whose first prefix segment is in ``reserved`` (registered model slugs) or
    whose router cannot be rebuilt is logged at ERROR and not mounted; models win.
    """
    routes: list[BaseRoute] = []
    for page in registry.pages:
        segment = page.prefix.split("/")[1]
        if segment in reserved:
            logger.error(
                "plugin %r page %s not mounted: %r is a registered model",
                page.plugin,
                page.prefix,
                segment,
                extra={"plugin": page.plugin},
            )
            continue
        try:
            routes.extend(_page_routes(page, route_class))
        except PluginError:
            logger.exception(
                "plugin %r page %s not mounted",
                page.plugin,
                page.prefix,
                extra={"plugin": page.plugin},
            )
    return routes


def resolve_plugin_nav(registry: PluginRegistry, router: Router) -> list[dict[str, Any]]:
    """Group plugin nav entries into sidebar sections with admin-relative URLs.

    Each section is ``{"title": str | None, "items": [...]}`` (``None`` renders as
    "Plugins"), in order of first appearance. An entry whose ``url_name`` does not
    resolve on ``router`` is logged at ERROR and left out, so it cannot break pages.
    """
    sections: dict[str | None, list[dict[str, Any]]] = {}
    for entry in registry.nav_entries:
        try:
            url = router.url_path_for(entry.url_name, **entry.url_params)
        except NoMatchFound:
            logger.error(
                "plugin %r nav entry %r skipped: no admin route named %r",
                entry.plugin,
                entry.label,
                entry.url_name,
                extra={"plugin": entry.plugin},
            )
            continue
        sections.setdefault(entry.section, []).append(
            {
                "name": entry.label,
                "url": str(url),
                "icon": entry.icon or "",
                "permission": entry.permission,
                "testid": entry.testid or f"sidebar-plugin-{entry.plugin}-{entry.url_name}",
            }
        )
    return [{"title": title, "items": items} for title, items in sections.items()]


def plugin_permission_rows(
    registry: PluginRegistry, *, taken: Collection[str]
) -> list[tuple[str, str, str]]:
    """``(codename, name, content_type)`` rows for plugin permissions not in ``taken``.

    A plugin codename that collides with a model codename is logged at ERROR and left
    out. ``content_type`` is ``plugin:<name>``, so plugin rows never pose as a model.
    """
    rows: list[tuple[str, str, str]] = []
    perm: PluginPermission
    for perm in registry.permissions:
        if perm.codename in taken:
            logger.error(
                "plugin %r permission %r not synced: a model already defines it",
                perm.plugin,
                perm.codename,
                extra={"plugin": perm.plugin},
            )
            continue
        rows.append((perm.codename, perm.name, f"plugin:{perm.plugin}"))
    return rows
