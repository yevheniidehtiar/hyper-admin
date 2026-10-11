"""Namespace-aware URL resolution for the isolated sub-app mount (BYOA SDD C.1).

When ``Admin.mount()`` attaches HyperAdmin as a named sub-app
(``app.mount(path, sub_app, name=settings.route_namespace)``), every admin
route name is registered under that namespace, so Starlette resolves it only
as ``f"{namespace}:{name}"`` — the plain name raises ``NoMatchFound`` from
inside the sub-app. In today's legacy "router" mode (``include_router``,
no sub-app), route names stay un-namespaced, and so does every *host* route
in either mode.

``admin_url_for`` and the Jinja ``url_for`` override it installs try the
namespaced name first and fall back to the plain name, so the ~25 existing
``url_for(...)`` calls in HyperAdmin's own templates need no editing, and a
host-overridden template that links to a host route keeps working.

The namespace is read from ``request.scope["hyperadmin"]``, never from
``app.state`` — in isolated mode ``state`` is shared with the host
(``sub_app.state = app.state``), so admin-private routing data must not live
there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jinja2 import pass_context
from starlette.datastructures import URL
from starlette.routing import NoMatchFound

if TYPE_CHECKING:
    from jinja2 import Environment
    from jinja2.runtime import Context
    from starlette.requests import Request

#: Key under ``request.scope`` that carries the admin's own routing data
#: (currently ``{"namespace": str | None}``), set by the mount machinery.
#: Never ``app.state``, which an isolated mount shares with the host.
SCOPE_KEY = "hyperadmin"


def _namespace(request: Request) -> str | None:
    """Return the admin route namespace for this request, if any."""
    info = request.scope.get(SCOPE_KEY)
    if isinstance(info, dict):
        namespace = info.get("namespace")
        if isinstance(namespace, str) and namespace:
            return namespace
    return None


def admin_url_for(request: Request, name: str, /, **path_params: Any) -> URL:
    """Resolve ``name`` to a URL, preferring the admin's own namespaced route.

    Tries ``f"{namespace}:{name}"`` when ``request.scope["hyperadmin"]``
    carries a namespace, then falls back to the plain ``name`` — which
    resolves an un-namespaced admin route (legacy "router" mount mode) and
    any host route exactly as ``request.url_for`` would.

    ``request`` and ``name`` are positional-only (matching Starlette's own
    ``url_for``, and the SDD's pinned signature) so a route with a path
    param literally named ``name`` or ``request`` resolves through
    ``**path_params`` instead of colliding with this function's own
    parameters.
    """
    namespace = _namespace(request)
    if namespace:
        try:
            return request.url_for(f"{namespace}:{name}", **path_params)
        except NoMatchFound:
            pass
    return request.url_for(name, **path_params)


def install_namespaced_url_for(env: Environment) -> None:
    """Replace the Jinja ``url_for`` global with a namespace-aware wrapper.

    Starlette's ``Jinja2Templates`` installs a plain ``url_for`` global with
    ``setdefault``; this overrides it so every ``{{ url_for(...) }}`` call in
    an admin template resolves through :func:`admin_url_for`.
    """

    @pass_context
    def url_for(ctx: Context, name: str, /, **path_params: Any) -> URL:
        request: Request = ctx["request"]
        return admin_url_for(request, name, **path_params)

    env.globals["url_for"] = url_for


def admin_base_path(request: Request) -> str:
    """Return the per-request external admin path, honouring the host's root_path.

    A host may itself run under a ``root_path`` (for example behind an
    ingress serving it at ``/api``), so the browser-visible admin path is not
    always the mount prefix string passed to ``admin.mount(prefix)``:

    - **Isolated mode** (the default, C.1): ``app.mount(prefix, sub_app)``
      already extends ``scope["root_path"]`` to the full external prefix, so
      it is returned as-is.
    - **Router mode** (legacy, ``include_router``): there is no sub-app to
      extend ``root_path``, so the admin prefix — kept on
      ``scope["hyperadmin"]["prefix"]`` by the mount machinery — is appended
      to the host's own ``root_path``.

    Returns ``scope["root_path"]`` unchanged when ``scope["hyperadmin"]``
    carries no namespace and no prefix, which is always true before
    ``admin.mount()`` has wired either (today's state).
    """
    scope = request.scope
    root_path = scope.get("root_path", "") or ""
    info = scope.get(SCOPE_KEY)
    if isinstance(info, dict) and info.get("namespace"):
        return root_path
    prefix = info.get("prefix", "") if isinstance(info, dict) else ""
    return f"{root_path}{prefix}"
