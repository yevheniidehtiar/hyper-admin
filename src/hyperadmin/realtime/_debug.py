"""Test-only HTTP endpoints for introspecting the realtime registry.

Mounted under ``{admin_prefix}/_test/realtime/`` only when
``RealtimeSettings.enable_test_endpoints`` is ``True``. The Playwright
suite uses these to assert server-side cleanup and simulate
server-initiated disconnects without restarting the process.

Never enable this flag in production: the endpoints expose connection
counts and let any caller force-disconnect every live client.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from hyperadmin.realtime.registry import ConnectionRegistry

Handler = Callable[[Request], Awaitable[Response]]


def make_count_handler(registry: ConnectionRegistry) -> Handler:
    async def count(_request: Request) -> Response:
        snap = registry.snapshot()
        return JSONResponse(
            {
                "count": len(snap),
                "users": sorted({c.user_id for c in snap}),
                "by_transport": {
                    "sse": sum(1 for c in snap if c.transport == "sse"),
                    "ws": sum(1 for c in snap if c.transport == "ws"),
                },
            }
        )

    return count


def make_disconnect_all_handler(registry: ConnectionRegistry) -> Handler:
    async def disconnect_all(_request: Request) -> Response:
        closed = await registry.close_where(lambda _c: True)
        return JSONResponse({"closed": closed})

    return disconnect_all


def make_disconnect_transport_handler(registry: ConnectionRegistry) -> Handler:
    async def disconnect_transport(request: Request) -> Response:
        transport = request.path_params["transport"]
        if transport not in ("sse", "ws"):
            return JSONResponse({"detail": "unknown transport"}, status_code=400)
        target: Literal["sse", "ws"] = transport
        closed = await registry.close_where(lambda c: c.transport == target)
        return JSONResponse({"closed": closed, "transport": transport})

    return disconnect_transport
